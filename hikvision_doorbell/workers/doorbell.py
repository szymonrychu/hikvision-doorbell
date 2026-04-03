import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, cast

import httpx
from aiomqtt import Client, ProtocolVersion
from pydantic import ValidationError

from hikvision_doorbell.helpers import PerMessageRateLimitFilter, retry_async_yield
from hikvision_doorbell.models.hikvision import (
    CallButtonStates,
    CallInfo,
    DeviceInfo,
    DoorInfo,
)
from hikvision_doorbell.models.mqtt import (
    MqttButtonDiscovery,
    MqttDiscoveryAvailability,
    MqttDiscoveryDevice,
    MqttLockDiscovery,
    MqttLockDiscoveryState,
    MqttMessageAvailabilityPayload,
)
from hikvision_doorbell.settings import settings

logger = logging.getLogger(__name__)
logger.addFilter(PerMessageRateLimitFilter(3600))

CALL_SLEEP_TIME = 0.5
REFRESH_SLEEP_TIME = 2


# ───────────────────────────────────────────────
# Hikvision client (async)
class Doorbell:
    def __init__(self):
        scheme = "https" if settings.HIK_HTTPS else "http"
        self._base_url = f"{scheme}://{settings.HIK_HOST}"
        self._client = None
        self._device_healthy = True
        self._device_info = None
        self._call_info = None
        self._reseted_availability = True
        _device = MqttDiscoveryDevice(
            identifiers=[f"hik_{settings.HIK_HOST.replace('.', '_')}"],
            manufacturer=settings.DEVICE_MANUFACTURER,
            model=settings.DEVICE_MODEL,
            name=settings.DEVICE_NAME,
        )
        self._ring_discovery = MqttButtonDiscovery(
            availability=MqttDiscoveryAvailability(
                topic="/".join([settings.MQTT_BASE_TOPIC.rstrip("/"), settings.DEVICE_SENSOR_NAME, "availability"])
            ),
            name=settings.DEVICE_SENSOR_NAME,
            unique_id=settings.DEVICE_SENSOR_UID,
            device=_device,
            event_types=[t.value for t in CallButtonStates],
            state_topic="/".join([settings.MQTT_BASE_TOPIC.rstrip("/"), settings.DEVICE_SENSOR_NAME, "state"]),
        )
        self._lock_discovery = MqttLockDiscovery(
            availability=MqttDiscoveryAvailability(
                topic="/".join([settings.MQTT_BASE_TOPIC.rstrip("/"), settings.DEVICE_LOCK_NAME, "availability"])
            ),
            name=settings.DEVICE_LOCK_NAME,
            unique_id=settings.DEVICE_LOCK_UID,
            device=_device,
            command_topic="/".join([settings.MQTT_BASE_TOPIC.rstrip("/"), settings.DEVICE_LOCK_NAME, "set"]),
            state_topic="/".join([settings.MQTT_BASE_TOPIC.rstrip("/"), settings.DEVICE_LOCK_NAME, "state"]),
        )
        self._discovery_list = [
            self._lock_discovery,
            self._ring_discovery,
        ]
        self.state_cache: Dict[str, Any] = {}

    def tasks(self, stop_event: asyncio.Event) -> List[asyncio.Task]:
        tasks = []
        for t in [
            self.handle_lock_command(stop_event),
            self.refresh_client(stop_event),
            self.handle_device_infos(stop_event),
            self.handle_call_statuses(stop_event),
        ]:
            tasks.append(asyncio.create_task(t))
        return tasks

    async def publish_if_changed(self, topic: str, value: str, retain=True):
        if self.state_cache.get(topic) == value:
            return
        logger.info(f"publishing event on topic: '{topic}', value: '{str(value)}'")
        self.state_cache[topic] = value
        try:
            async with Client(
                hostname=settings.MQTT_HOST,
                port=settings.MQTT_PORT,
                username=settings.MQTT_USER,
                password=settings.MQTT_PASS,
                protocol=ProtocolVersion.V311,
            ) as mqtt:
                await mqtt.publish(topic, str(value).encode("utf-8"), qos=1, retain=retain)
        except Exception as e:
            logger.warning("MQTT publish failed for topic %r: %s", topic, e)

    async def publish_discovery(self):
        try:
            async with Client(
                hostname=settings.MQTT_HOST,
                port=settings.MQTT_PORT,
                username=settings.MQTT_USER,
                password=settings.MQTT_PASS,
                protocol=ProtocolVersion.V311,
            ) as mqtt:
                for discovery in self._discovery_list:
                    await discovery.publish_discovery(mqtt, settings.MQTT_DISCOVERY_PREFIX)
        except Exception as e:
            logger.warning("MQTT discovery publish failed: %s", e)

    async def publish_availability(self, available: bool):
        for discovery in self._discovery_list:
            a = (
                MqttMessageAvailabilityPayload.payload_available
                if available
                else MqttMessageAvailabilityPayload.payload_not_available
            )
            await self.publish_if_changed(discovery.availability.topic, a.value)
        if not available:
            self._reseted_availability = True

    async def handle_lock_command(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                async with Client(
                    hostname=settings.MQTT_HOST,
                    port=settings.MQTT_PORT,
                    username=settings.MQTT_USER,
                    password=settings.MQTT_PASS,
                    protocol=ProtocolVersion.V311,
                ) as mqtt:
                    await mqtt.subscribe(self._lock_discovery.command_topic)
                    logger.info(f"Subscribed to: {self._lock_discovery.command_topic}")

                    async for msg in mqtt.messages:
                        if stop_event.is_set():
                            break
                        if str(msg.topic) != self._lock_discovery.command_topic:
                            continue  # ignore other messages

                        door_state = await self.open_close_doors(True)
                        if door_state != DoorInfo.opened:
                            await self.publish_if_changed(
                                self._lock_discovery.state_topic, MqttLockDiscoveryState.jammed.value
                            )
                            continue
                        await self.publish_if_changed(
                            self._lock_discovery.state_topic, MqttLockDiscoveryState.unlocked.value
                        )

                        await asyncio.sleep(settings.DEVICE_UNLOCK_SLEEP_TIME_S)
                        door_state = await self.open_close_doors(False)
                        if not settings.DEVICE_AUTOLOCKING:
                            if door_state != DoorInfo.closed:
                                await self.publish_if_changed(
                                    self._lock_discovery.state_topic, MqttLockDiscoveryState.jammed.value
                                )
                                continue
                        await self.publish_if_changed(
                            self._lock_discovery.state_topic, MqttLockDiscoveryState.locked.value
                        )
            except Exception as e:
                logger.warning("MQTT lock command handler failed: %s", e)
                await asyncio.sleep(5)

    async def get_device_info(self) -> DeviceInfo | None:
        return self._device_info

    async def get_call_info(self) -> CallInfo | None:
        return self._call_info

    async def device_healthy(self) -> bool:
        return self._device_healthy

    def _url(self, path: str) -> str:
        if path.startswith("/"):
            path = path[1:]
        return f"{self._base_url}/{path}"

    @retry_async_yield(
        settings.DEVICE_CALL_RETRY_MAX_COUNT,
        settings.DEVICE_CALL_RETRY_DELAY,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout),
    )
    async def _get_device_info(self, client: httpx.AsyncClient) -> DeviceInfo | None:
        url = self._url("/ISAPI/System/deviceInfo")
        resp = await client.get(url)
        if resp.status_code not in (200, 204):
            return None
        try:
            return DeviceInfo.from_xml(resp.content.decode("utf-8"))
        except (ET.ParseError, ValueError, ValidationError) as e:
            logger.warning("Failed to parse device info XML: %s", e)
            return None

    def _parse_call_status(self, data: Dict[str, Any]) -> CallInfo | None:
        """Safely parse call status from JSON; returns None for unknown/missing values."""
        status = (data.get("CallStatus") or {}).get("status")
        if status is None:
            return None
        try:
            return CallInfo(status)
        except ValueError:
            logger.warning("Unknown call status from device: %r", status)
            return None

    @retry_async_yield(
        settings.DEVICE_CALL_RETRY_MAX_COUNT,
        settings.DEVICE_CALL_RETRY_DELAY,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout),
    )
    async def _get_call_status(self, client: httpx.AsyncClient) -> CallInfo | None:
        url = self._url("/ISAPI/VideoIntercom/callStatus")
        resp = await client.get(url)
        if resp.status_code not in (200, 204):
            return None
        try:
            data = json.loads(resp.content)
            return self._parse_call_status(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse call status JSON: %s", e)
            return None

    @retry_async_yield(
        settings.DEVICE_CALL_RETRY_MAX_COUNT,
        settings.DEVICE_CALL_RETRY_DELAY,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout),
    )
    async def _open_close_doors(self, client: httpx.AsyncClient, open: bool) -> DoorInfo | None:
        path = f"/ISAPI/AccessControl/RemoteControl/door/{(settings.DOOR_RELAY_ID)}"
        url = self._url(path)
        open_close = "open" if open else "close"
        xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<RemoteControlDoor>
  <cmd>{open_close}</cmd>
</RemoteControlDoor>
"""
        resp = await client.put(url, content=xml_body.encode("utf-8"))
        if resp.status_code in (200, 204):
            status = DoorInfo.opened if open else DoorInfo.closed
            logger.info(f"{status.value} doors")
            return status
        return None

    async def open_close_doors(self, open: bool) -> DoorInfo:
        if self._client is None:
            self._device_healthy = False
            return DoorInfo.jammed
        try:
            attempt = None
            async for attempt in self._open_close_doors(self._client, open):
                if not attempt:
                    self._device_healthy = False
                else:
                    self._device_healthy = True
                    return cast(DoorInfo, attempt)
            return DoorInfo.jammed
        except Exception as e:
            logger.warning("Open/close doors failed after retries: %s", e)
            self._device_healthy = False
            return DoorInfo.jammed

    async def refresh_client(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            if self._client is not None:
                await self._client.aclose()
            self._client = httpx.AsyncClient(
                auth=httpx.DigestAuth(settings.HIK_USERNAME, settings.HIK_PASSWORD), timeout=1
            )
            await asyncio.sleep(REFRESH_SLEEP_TIME)

    async def handle_device_infos(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            if not self._client:
                logger.info("waiting for client")
                await asyncio.sleep(0.1)
                continue

            try:
                async for attempt in self._get_device_info(self._client):
                    if not attempt:
                        logger.info("can't get call device info")
                        self._device_healthy = False
                        await self.publish_availability(False)
                    else:
                        await self.publish_availability(True)
                        if self._reseted_availability:
                            await self.publish_if_changed(
                                self._lock_discovery.state_topic,
                                DoorInfo.closed.to_mqtt_lock_discovery_state().value,
                            )
                            self._reseted_availability = False
                        self._device_info = cast(DeviceInfo, attempt)
            except Exception as e:
                logger.warning("Device info fetch failed after retries: %s", e)
                self._device_healthy = False
                await self.publish_availability(False)

            await asyncio.sleep(CALL_SLEEP_TIME)

    async def handle_call_statuses(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            if not self._client:
                logger.info("waiting for client")
                await asyncio.sleep(0.1)
                continue

            try:
                async for attempt in self._get_call_status(self._client):
                    if not attempt:
                        await self.publish_if_changed(self._ring_discovery.state_topic, CallButtonStates.unknown.value)

                    if attempt:
                        info = cast(CallInfo, attempt)
                        if info == CallInfo.ring:
                            await self.publish_if_changed(
                                self._ring_discovery.state_topic, CallButtonStates.pressed.value
                            )
                            await asyncio.sleep(1)
                            await self.publish_if_changed(
                                self._ring_discovery.state_topic, CallButtonStates.released.value
                            )
                        else:
                            await self.publish_if_changed(
                                self._ring_discovery.state_topic,
                                info.to_mqtt_event_discovery_event_type(),
                            )
            except Exception as e:
                logger.warning("Call status fetch failed after retries: %s", e)
                await self.publish_if_changed(self._ring_discovery.state_topic, CallButtonStates.unknown.value)

            await asyncio.sleep(CALL_SLEEP_TIME)


doorbell = Doorbell()
