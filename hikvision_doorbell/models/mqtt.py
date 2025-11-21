import logging
from enum import Enum
from typing import List

from aiomqtt import Client
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MqttBaseModel(BaseModel):
    ...
    # class Config:
    #     use_enum_values = True


class MqttMessageAvailabilityPayload(Enum):
    payload_available = "online"
    payload_not_available = "offline"


class MqttDiscoveryType(Enum):
    button = "button"
    sensor = "sensor"
    lock = "lock"
    event = "event"


class MqttDiscoveryAvailability(MqttBaseModel):
    payload_available: str = MqttMessageAvailabilityPayload.payload_available.value
    payload_not_available: str = MqttMessageAvailabilityPayload.payload_not_available.value
    topic: str
    value_template: str | None = None


class MqttDiscoveryDevice(MqttBaseModel):
    identifiers: List[str]
    manufacturer: str
    model: str
    name: str


class MqttMessage(MqttBaseModel):
    state_topic: str | None
    command_topic: str | None
    payload: Enum
    availability_topic: str
    availability_payload: MqttMessageAvailabilityPayload = MqttMessageAvailabilityPayload.payload_available


class MqttDiscovery(MqttBaseModel):
    availability: MqttDiscoveryAvailability
    command_topic: str | None = None
    state_topic: str | None = None
    name: str
    unique_id: str
    type: MqttDiscoveryType
    device: MqttDiscoveryDevice
    enabled_by_default: bool = True

    async def publish_discovery(self, discovery_prefix: str, mqtt: Client):
        await mqtt.publish(
            "/".join([discovery_prefix, self.type.value, self.unique_id, "config"]),
            self.model_dump_json(exclude_none=True),
            qos=1,
            retain=True,
        )

    async def get_mqtt_message(
        self, payload: Enum, availability: MqttMessageAvailabilityPayload | None = None
    ) -> MqttMessage:
        return MqttMessage(
            command_topic=self.command_topic,
            state_topic=self.state_topic,
            payload=payload,
            availability_topic=self.availability.topic,
            availability_payload=availability or MqttMessageAvailabilityPayload.payload_available,
        )


class MqttButtonDiscoveryDeviceClass(Enum):
    identify = "identify"
    restart = "restart"
    update = "update"


class MqttButtonDiscoveryPlatform(Enum):
    button = "button"


class MqttButtonDiscovery(MqttDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.button
    device_class: MqttButtonDiscoveryDeviceClass | None = None
    platform: MqttButtonDiscoveryPlatform = MqttButtonDiscoveryPlatform.button


class MqttSensorDiscoveryPlatform(Enum):
    sensor = "sensor"


class MqttSensorDiscovery(MqttDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.sensor
    value_template: str | None = None
    json_attributes_topic: str | None = None
    device_class: str | None = None
    platform: MqttSensorDiscoveryPlatform = MqttSensorDiscoveryPlatform.sensor


class MqttEventDiscoveryPlatform(Enum):
    event = "event"


class MqttEventDiscoveryEventTypes(Enum):
    idle = "idle"
    ring = "ring"
    calling = "onCall"
    unknown = "unknown"


class MqttEventDiscoveryDeviceClass(Enum):
    button = "button"
    doorbell = "doorbell"
    motion = "motion"


class MqttEventDiscovery(MqttDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.lock
    device_class: MqttEventDiscoveryDeviceClass
    event_types: List[str] = [e.value for e in MqttEventDiscoveryEventTypes]
    platform: MqttEventDiscoveryPlatform = MqttEventDiscoveryPlatform.event


class MqttLockDiscoveryDeviceClass(Enum):
    identify = "identify"
    restart = "restart"
    update = "update"


class MqttLockDiscoveryPlatform(Enum):
    lock = "lock"


class MqttLockDiscoveryState(Enum):
    lock = "LOCK"
    unlock = "UNLOCK"
    jammed = "JAMMED"
    locked = "LOCKED"
    unlocked = "UNLOCKED"


class MqttLockDiscovery(MqttDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.lock
    optimistic: bool = False
    payload_lock: MqttLockDiscoveryState = MqttLockDiscoveryState.lock
    payload_unlock: MqttLockDiscoveryState = MqttLockDiscoveryState.unlock
    platform: MqttLockDiscoveryPlatform = MqttLockDiscoveryPlatform.lock
    state_jammed: MqttLockDiscoveryState = MqttLockDiscoveryState.jammed
    state_locked: MqttLockDiscoveryState = MqttLockDiscoveryState.locked
    state_unlocked: MqttLockDiscoveryState = MqttLockDiscoveryState.unlocked


class CallStateEvent(Enum):
    idle = "idle"
    ring = "ring"
    calling = "onCall"
    error = "error"


# class MqttEvent(BaseModel):
#     event: CallStateEvent
#     channel_id: Optional[str] = None
#     rule_name: Optional[str] = None
#     raw: Dict[str, Any] = {}


# # ───────────────────────────────────────────────
# # Event model
# class DoorbellEvent(BaseModel):
#     event_type: str
#     ip_address: Optional[str]
#     channel_id: Optional[str]
#     rule_name: Optional[str]
#     timestamp: Optional[str]
#     raw: Dict[str, Any]

#     @classmethod
#     def from_xml_block(cls, xml_block: str) -> Optional["DoorbellEvent"]:
#         try:
#             root = ET.fromstring(xml_block)
#         except ET.ParseError as e:
#             logger.debug(f"XML parse error: {e}")
#             return None

#         data: Dict[str, Any] = {}
#         for child in root:
#             data[child.tag] = (child.text or "").strip()

#         ev_type = data.get("eventType") or data.get("EventType") or "unknown"
#         return cls(
#             event_type=ev_type,
#             ip_address=data.get("ipAddress"),
#             channel_id=data.get("channelID") or data.get("channelId"),
#             rule_name=data.get("ruleName"),
#             timestamp=data.get("time"),
#             raw=data,
#         )
