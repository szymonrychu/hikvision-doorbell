import asyncio
import logging
from typing import Any, Dict

from aiomqtt import Client, MqttError, ProtocolVersion

from hikvision_doorbell.hikvision_client import client
from hikvision_doorbell.models.mqtt import (
    MqttDiscoveryAvailability,
    MqttDiscoveryDevice,
    MqttEventDiscovery,
    MqttEventDiscoveryDeviceClass,
    MqttLockDiscovery,
    MqttLockDiscoveryState,
    MqttMessage,
)
from hikvision_doorbell.settings import settings

logger = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(self):
        self.settings = settings
        self.base = settings.MQTT_BASE_TOPIC.rstrip("/")
        self.discovery_prefix = settings.MQTT_DISCOVERY_PREFIX.rstrip("/")
        self._lock_event_queue: asyncio.Queue = asyncio.Queue()
        self._ring_event_queue: asyncio.Queue = asyncio.Queue()

        _device = MqttDiscoveryDevice(
            identifiers=[f"hik_{settings.HIK_HOST.replace('.', '_')}"],
            manufacturer=settings.DEVICE_MANUFACTURER,
            model=settings.DEVICE_MODEL,
            name=settings.DEVICE_NAME,
        )
        _availability = MqttDiscoveryAvailability(topic="/".join([self.base, "availability"]))

        self._event_discovery = MqttEventDiscovery(
            availability=MqttDiscoveryAvailability(
                topic="/".join([self.base, settings.DEVICE_SENSOR_NAME, "availability"])
            ),
            name=settings.DEVICE_SENSOR_NAME,
            unique_id=settings.DEVICE_SENSOR_UID,
            device=_device,
            device_class=MqttEventDiscoveryDeviceClass.doorbell,
            state_topic="/".join([self.base, settings.DEVICE_SENSOR_NAME, "state"]),
        )
        self._lock_discovery = MqttLockDiscovery(
            availability=MqttDiscoveryAvailability(
                topic="/".join([self.base, settings.DEVICE_LOCK_NAME, "availability"])
            ),
            name=settings.DEVICE_LOCK_NAME,
            unique_id=settings.DEVICE_LOCK_UID,
            device=_device,
            command_topic="/".join([self.base, settings.DEVICE_LOCK_NAME, "set"]),
            state_topic="/".join([self.base, settings.DEVICE_LOCK_NAME, "state"]),
        )
        self.discovery_sent_once = False  # Never reset

        self.state_cache: Dict[str, Any] = {}

    # ─────────────────────────
    async def publish_discovery_once(self, mqtt: Client):
        if self.discovery_sent_once:
            return  # Already sent once after start → do nothing
        logger.debug("publishing discovery messages")
        await self._event_discovery.publish_discovery(self.discovery_prefix, mqtt)
        await self._lock_discovery.publish_discovery(self.discovery_prefix, mqtt)
        await self._lock_event_queue.put(await self._lock_discovery.get_mqtt_message(MqttLockDiscoveryState.locked))
        await self._publish_if_changed(mqtt, self._lock_discovery.state_topic, MqttLockDiscoveryState.locked.value)
        self.discovery_sent_once = True  # Never reset

    async def _publish_if_changed(self, mqtt: Client, topic: str, value: str, *, retain=True):
        if self.state_cache.get(topic) == value:
            return
        self.state_cache[topic] = value
        logger.debug(f"publishing event on topic: '{topic}', value: '{str(value)}'")
        await mqtt.publish(topic, str(value).encode("utf-8"), qos=1, retain=retain)

    # ───────────────────────────────────────────────
    async def handle_mqtt_commands(self, mqtt: Client, stop_event: asyncio.Event):
        while not stop_event.is_set():
            await mqtt.subscribe(self._lock_discovery.command_topic)
            logger.debug(f"Subscribed to: {self._lock_discovery.command_topic}")

            async for msg in mqtt.messages:
                if str(msg.topic) != self._lock_discovery.command_topic:
                    continue  # ignore other messages

                if await client.ensure_door_state(True):
                    logger.info("Opened doors!")
                    await self._publish_if_changed(
                        mqtt, self._lock_discovery.state_topic, MqttLockDiscoveryState.unlocked.value
                    )
                    await asyncio.sleep(10)
                    await self._publish_if_changed(
                        mqtt, self._lock_discovery.state_topic, MqttLockDiscoveryState.locked.value
                    )
                else:
                    logger.warning("Problem opening doors!")

    async def process_events(self, queue: asyncio.Queue, mqtt: Client, stop_event: asyncio.Event):
        while not stop_event.is_set():
            m: MqttMessage = await queue.get()

            await self._publish_if_changed(mqtt, m.availability_topic, m.availability_payload.value)
            if m.state_topic and m.payload:
                await self._publish_if_changed(mqtt, m.state_topic, m.payload.value)

    async def run(self):
        stop_event = asyncio.Event()
        async with Client(
            hostname=self.settings.MQTT_HOST,
            port=self.settings.MQTT_PORT,
            username=self.settings.MQTT_USER,
            password=self.settings.MQTT_PASS,
            protocol=ProtocolVersion.V311,
        ) as mqtt:
            try:
                await self.publish_discovery_once(mqtt)
                tasks = [
                    asyncio.create_task(client.refresh_client(stop_event)),
                    asyncio.create_task(
                        client.stream_call_statuses(self._ring_event_queue, self._event_discovery, stop_event)
                    ),
                    asyncio.create_task(self.handle_mqtt_commands(mqtt, stop_event)),
                    asyncio.create_task(self.process_events(self._ring_event_queue, mqtt, stop_event)),
                    asyncio.create_task(self.process_events(self._lock_event_queue, mqtt, stop_event)),
                ]
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for t in pending:
                    t.cancel()
            except MqttError as me:
                logger.warning(f"MQTT error: {me}")
                await asyncio.sleep(10)


bridge = MQTTBridge()
