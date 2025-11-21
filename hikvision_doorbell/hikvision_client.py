import asyncio
import json
import logging

import httpx

from hikvision_doorbell.models.mqtt import (
    CallStateEvent,
    MqttEventDiscovery,
    MqttEventDiscoveryEventTypes,
    MqttLockDiscoveryState,
    MqttMessageAvailabilityPayload,
)
from hikvision_doorbell.settings import settings

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# Hikvision client (async)
class HikvisionClient:
    def __init__(self):
        scheme = "https" if settings.HIK_HTTPS else "http"
        self.base_url = f"{scheme}://{settings.HIK_HOST}"
        self.settings = settings
        self._raw_events_buffer = ""
        self._client = None

    def _url(self, path: str) -> str:
        if path.startswith("/"):
            path = path[1:]
        return f"{self.base_url}/{path}"

    async def get_snapshot(self, channel: int = 1) -> bytes:
        path = f"/ISAPI/Streaming/channels/{channel:02d}1/picture"
        url = self._url(path)
        client = httpx.AsyncClient(auth=httpx.DigestAuth(settings.HIK_USERNAME, settings.HIK_PASSWORD), timeout=10)
        resp = await client.get(url)
        resp.raise_for_status()
        if "image" in resp.headers.get("Content-Type", ""):
            return resp.content
        else:
            raise RuntimeError(f"Snapshot response wrong content‑type: {resp.headers.get('Content-Type')}")

    async def change_door_state(self, relay_id: int, open: bool) -> bool:
        path = f"/ISAPI/AccessControl/RemoteControl/door/{relay_id}"
        url = self._url(path)
        open_close = "open" if open else "close"
        xml_body = f"""<?xml version="1.0" encoding="UTF‑8"?>
<RemoteControlDoor>
  <cmd>{open_close}</cmd>
</RemoteControlDoor>
"""
        headers = {"Content-Type": "application/xml", "Accept": "application/xml"}
        resp = await self._client.put(url, content=xml_body.encode("utf‑8"), headers=headers)
        # Hitch: some devices return 204, some 200
        if resp.status_code in (200, 204):
            return True
        return False

    async def get_call_status(self, client: httpx.AsyncClient | None = None) -> CallStateEvent:
        url = self._url("/ISAPI/VideoIntercom/callStatus")
        headers = {"Content-Type": "application/xml", "Accept": "application/xml"}
        client = client or httpx.AsyncClient(
            auth=httpx.DigestAuth(settings.HIK_USERNAME, settings.HIK_PASSWORD), timeout=10
        )
        resp = await client.get(url, headers=headers)
        try:
            if resp.status_code in (200, 204):
                data = json.loads(resp.content)
                return CallStateEvent[data["CallStatus"]["status"]]
        except json.JSONDecodeError:
            logger.error(f"Couldn't parse json '{resp.content}'")
        except ValueError:
            logger.error(f"Couldn't parse '{resp.content}'")
        except KeyError:
            logger.error(f"Couldn't get keys from '{resp.content}'")
        return CallStateEvent.error

    async def ensure_door_state(self, open: bool, retry_count: int = 10) -> MqttLockDiscoveryState:
        path = f"/ISAPI/AccessControl/RemoteControl/door/{(self.settings.DOOR_RELAY_ID)}"
        headers = {"Content-Type": "application/xml", "Accept": "application/xml"}
        url = self._url(path)
        open_close = "open" if open else "close"
        xml_body = f"""<?xml version="1.0" encoding="UTF‑8"?>
<RemoteControlDoor>
  <cmd>{open_close}</cmd>
</RemoteControlDoor>
"""
        for _ in range(retry_count):
            while not self._client:
                logger.debug("waiting for client")
                await asyncio.sleep(0.1)
            resp = await self._client.put(url, content=xml_body.encode("utf‑8"), headers=headers)
            # Hitch: some devices return 204, some 200
            if resp.status_code in (200, 204):
                return MqttLockDiscoveryState.unlocked if open else MqttLockDiscoveryState.locked
            logger.debug(f"{resp.content}")
            await asyncio.sleep(1)
        return MqttLockDiscoveryState.jammed

    async def refresh_client(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            logger.debug("refreshing client")
            self._client = httpx.AsyncClient(
                auth=httpx.DigestAuth(settings.HIK_USERNAME, settings.HIK_PASSWORD),
                timeout=httpx.Timeout(None, read=None),
            )
            await asyncio.sleep(1)

    async def stream_call_statuses(
        self, event_queue: asyncio.Queue, event_discovery: MqttEventDiscovery, stop_event: asyncio.Event
    ):
        while not stop_event.is_set():
            if not self._client:
                logger.debug("waiting for client")
                await asyncio.sleep(0.1)
                continue
            try:
                call_status = await self.get_call_status(self._client)
                await event_queue.put(await event_discovery.get_mqtt_message(call_status))
            except httpx.ConnectError as e:
                await event_queue.put(
                    await event_discovery.get_mqtt_message(
                        MqttEventDiscoveryEventTypes.unknown, MqttMessageAvailabilityPayload.payload_not_available
                    )
                )
                logger.warning(f"Event stream connection error {str(e)}, reconnecting...")
                await asyncio.sleep(1)

            except httpx.ConnectTimeout as e:
                await event_queue.put(
                    await event_discovery.get_mqtt_message(
                        MqttEventDiscoveryEventTypes.unknown, MqttMessageAvailabilityPayload.payload_not_available
                    )
                )
                logger.warning(f"Event stream connection timeout {str(e)}, reconnecting...")
                await asyncio.sleep(1)

            except httpx.ReadError as e:
                await event_queue.put(
                    await event_discovery.get_mqtt_message(
                        MqttEventDiscoveryEventTypes.unknown, MqttMessageAvailabilityPayload.payload_not_available
                    )
                )
                logger.warning(f"Event stream read error {str(e)}, reconnecting...")
                await asyncio.sleep(1)

            except httpx.ReadTimeout as e:
                await event_queue.put(
                    await event_discovery.get_mqtt_message(
                        MqttEventDiscoveryEventTypes.unknown, MqttMessageAvailabilityPayload.payload_not_available
                    )
                )
                logger.warning(f"Event stream read timeout {str(e)}, reconnecting...")
                await asyncio.sleep(1)

            except Exception as e:
                await event_queue.put(
                    await event_discovery.get_mqtt_message(
                        MqttEventDiscoveryEventTypes.unknown, MqttMessageAvailabilityPayload.payload_not_available
                    )
                )
                logger.exception(f"Event stream crashed {str(e)}, retrying...")
                await asyncio.sleep(1)

    # async def stream_events(self, event_queue: asyncio.Queue, stop_event: asyncio.Event):
    #     alert_stream_url = self._url("/ISAPI/Event/notification/alertStream")

    #     headers = {"Accept": "application/xml"}

    #     while not stop_event.is_set():
    #         if not self._client:
    #             logger.debug("waiting for client")
    #             await asyncio.sleep(0.1)
    #             continue
    #         try:
    #             async with self._client.stream("GET", alert_stream_url, headers=headers) as resp:
    #                 if resp.status_code != 200:
    #                     logger.error(f"Event stream error {resp.status_code}")
    #                     await event_queue.put(MqttEvent(event=CallStateEvent.error))
    #                     await asyncio.sleep(1)
    #                     continue

    #                 async for chunk in resp.aiter_text(chunk_size=1024):
    #                     if stop_event.is_set():
    #                         return
    #                     self._raw_events_buffer += chunk
    #                     while "</EventNotificationAlert>" in self._raw_events_buffer:
    #                         logger.debug(f"processing events from buffer, len={len(self._raw_events_buffer)}")
    #                         end = self._raw_events_buffer.index("</EventNotificationAlert>") + len(
    #                             "</EventNotificationAlert>"
    #                         )
    #                         xml_block = self._raw_events_buffer[:end]
    #                         self._raw_events_buffer = self._raw_events_buffer[end:]
    #                         logger.debug(f"Received raw event: {xml_block}")
    #                         ev = DoorbellEvent.from_xml_block(xml_block)
    #                         if ev:
    #                             logger.info(f"Received new event {ev.event_type}")
    #                             await event_queue.put(ev)
    #             await asyncio.sleep(0.5)

    #         except httpx.ConnectError as e:
    #             await event_queue.put(MqttEvent(event=CallStateEvent.error))
    #             logger.warning(f"Event stream connection error {str(e)}, reconnecting...")
    #             await asyncio.sleep(1)

    #         except httpx.ConnectTimeout as e:
    #             await event_queue.put(MqttEvent(event=CallStateEvent.error))
    #             logger.warning(f"Event stream connection timeout {str(e)}, reconnecting...")
    #             await asyncio.sleep(1)

    #         except httpx.ReadError as e:
    #             await event_queue.put(MqttEvent(event=CallStateEvent.error))
    #             logger.warning(f"Event stream read error {str(e)}, reconnecting...")
    #             await asyncio.sleep(1)

    #         except httpx.ReadTimeout as e:
    #             await event_queue.put(MqttEvent(event=CallStateEvent.error))
    #             logger.warning(f"Event stream read timeout {str(e)}, reconnecting...")
    #             await asyncio.sleep(1)

    #         except Exception as e:
    #             await event_queue.put(MqttEvent(event=CallStateEvent.error))
    #             logger.exception(f"Event stream crashed {str(e)}, retrying...")
    #             await asyncio.sleep(1)


client = HikvisionClient()
