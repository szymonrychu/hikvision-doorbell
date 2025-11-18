import asyncio
import json
import logging
from typing import Any, Dict, List

from aiomqtt import Client, MqttError, ProtocolVersion

from hikvision_doorbell.hikvision_client import client
from hikvision_doorbell.models.mqtt import DoorbellEvent
from hikvision_doorbell.settings import settings

logger = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(self):
        self.settings = settings
        self.base = settings.MQTT_BASE_TOPIC.rstrip("/")
        self.discovery_prefix = settings.MQTT_DISCOVERY_PREFIX.rstrip("/")

        # Topics
        self.topic_lock_cmd = f"{self.base}/lock/set"
        self.topic_lock_state = f"{self.base}/lock/state"
        self.topic_last_event = f"{self.base}/last_event"
        self.topic_snapshot = f"{self.base}/snapshot"
        self.discovery_sent_once = False  # Never reset

        id_base = f"hik_{settings.HIK_HOST.replace('.', '_')}"
        self.device = {
            "identifiers": [id_base],
            "manufacturer": settings.DEVICE_MANUFACTURER,
            "model": settings.DEVICE_MODEL,
            "name": settings.DEVICE_NAME,
        }
        self.uids = {
            "button": f"{id_base}_button",
            "lock": f"{id_base}_lock",
            "sensor": f"{id_base}_sensor",
            "camera": f"{id_base}_camera",
        }
        self.state_cache: Dict[str, Any] = {}

    # ───────────────────────────────────────────────
    # Home Assistant Discovery
    def _disc_topic(self, component: str, object_id: str) -> str:
        return f"{self.discovery_prefix}/{component}/{object_id}/config"

    def _make_discovery_payloads(self) -> List[tuple]:
        return [
            (
                self._disc_topic("switch", self.uids["lock"]),
                {
                    "name": f"{self.settings.DEVICE_NAME} Unlock",
                    "command_topic": self.topic_lock_cmd,
                    "unique_id": self.uids["lock"],
                    "device": self.device,
                    "type": "button",
                },
            ),
            (
                self._disc_topic("sensor", self.uids["sensor"]),
                {
                    "name": f"{self.settings.DEVICE_NAME} Last Event",
                    "state_topic": self.topic_last_event,
                    "value_template": "{{ value_json.event }}",
                    "json_attributes_topic": self.topic_last_event,
                    "unique_id": self.uids["sensor"],
                    "device": self.device,
                },
            ),
        ]

    async def publish_discovery_once(self, mqtt: Client):
        if self.discovery_sent_once:
            return  # Already sent once after start → do nothing
        logger.debug("publishing discovery messages")
        for topic, payload in self._make_discovery_payloads():
            await mqtt.publish(
                topic,
                json.dumps(payload).encode("utf-8"),
                qos=1,
                retain=True,
            )

        self.discovery_sent_once = True  # Never reset

    async def _publish_if_changed(self, mqtt: Client, topic: str, value: Any, *, retain=True):
        if self.state_cache.get(topic) == value:
            return
        self.state_cache[topic] = value
        logger.debug(f"publishing event on topic: '{topic}', value: '{str(value)}'")
        await mqtt.publish(topic, str(value).encode("utf-8"), qos=1, retain=retain)

    # ───────────────────────────────────────────────
    async def handle_mqtt_commands(self, mqtt: Client, stop_event: asyncio.Event):
        while not stop_event.is_set():
            await mqtt.subscribe(self.topic_lock_cmd)
            logger.debug(f"Subscribed to: {self.topic_lock_cmd}")

            async for msg in mqtt.messages:
                if str(msg.topic) != self.topic_lock_cmd:
                    continue  # ignore other messages

                if await client.ensure_door_state(True):
                    logger.info("Opened doors!")
                    await self._publish_if_changed(mqtt, self.topic_lock_state, "ON")
                else:
                    logger.warning("Problem opening doors!")

    async def process_events(self, mqtt: Client, event_queue: asyncio.Queue, stop_event: asyncio.Event):
        while not stop_event.is_set():
            ev: DoorbellEvent = await event_queue.get()

            # Publish last event (deduplicated)
            await self._publish_if_changed(mqtt, self.topic_last_event, ev.model_dump_json(exclude_none=True))

    async def run(self):
        event_queue: asyncio.Queue = asyncio.Queue()
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
                    asyncio.create_task(client.stream_events(event_queue, stop_event)),
                    asyncio.create_task(client.stream_call_statuses(event_queue, stop_event)),
                    asyncio.create_task(self.handle_mqtt_commands(mqtt, stop_event)),
                    asyncio.create_task(self.process_events(mqtt, event_queue, stop_event)),
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
