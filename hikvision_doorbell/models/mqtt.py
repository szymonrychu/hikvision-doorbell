import logging
from enum import Enum

from aiomqtt import Client
from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)


class MqttMessage(BaseModel):
    topic: str
    payload: str


class MqttMessageAvailabilityPayload(Enum):
    payload_available = "online"
    payload_not_available = "offline"


class MqttDiscoveryType(Enum):
    button = "button"
    sensor = "sensor"
    lock = "lock"
    event = "event"
    binary_sensor = "binary_sensor"


class MqttDiscoveryDeviceClass(Enum):
    button = "button"
    occupancy = "occupancy"
    identify = "identify"
    restart = "restart"
    update = "update"
    doorbell = "doorbell"
    motion = "motion"
    lock = "lock"


class MqttDiscoveryAvailability(BaseModel):
    payload_available: str = MqttMessageAvailabilityPayload.payload_available.value
    payload_not_available: str = MqttMessageAvailabilityPayload.payload_not_available.value
    topic: str


class MqttDiscoveryDevice(BaseModel):
    identifiers: list[str]
    manufacturer: str
    model: str
    name: str


# Device classes Home Assistant accepts per MQTT platform.
VALID_DEVICE_CLASSES = {
    "button": {"identify", "restart", "update"},
    "event": {"button", "doorbell", "motion"},
    "lock": set(),
    "sensor": set(),
    "binary_sensor": {"motion", "occupancy", "lock"},
}

# Retained discovery topics ("{prefix}" is the discovery prefix) that earlier versions published with
# schemas Home Assistant rejects and that this publisher no longer uses. Broker-side clean-up
# (ha-admin-ops-list) reads them from here.
LEGACY_DISCOVERY_TOPICS = (
    "{prefix}/event/doorbell_state_lock/config",
    "{prefix}/lock/doorbell_state_sensor/config",
    "{prefix}/binary_sensor/hik_192_168_1_55_button/config",
    "{prefix}/button/doorbell_state_sensor/config",
)


class MqttDiscovery(BaseModel):
    availability: MqttDiscoveryAvailability | None
    command_topic: str | None = None
    state_topic: str | None = None
    name: str
    unique_id: str
    type: MqttDiscoveryType
    device: MqttDiscoveryDevice
    enabled_by_default: bool = True
    device_class: MqttDiscoveryDeviceClass | None

    @model_validator(mode="after")
    def _validate_schema(self):
        component = self.type.value
        if component == "lock" and not self.command_topic:
            raise ValueError("lock discovery requires command_topic")
        if component == "event":
            if not self.state_topic:
                raise ValueError("event discovery requires state_topic")
            if not getattr(self, "event_types", None):
                raise ValueError("event discovery requires non-empty event_types")
        if self.device_class is not None and self.device_class.value not in VALID_DEVICE_CLASSES[component]:
            raise ValueError(f"device_class '{self.device_class.value}' is invalid for {component}")
        return self

    async def publish_discovery(self, mqtt: Client, discovery_prefix: str):
        # the topic component comes from the same field that selects the schema
        discovery_topic = "/".join([discovery_prefix, self.type.value, self.unique_id, "config"])
        model = self.model_dump_json(
            exclude_none=True,
            include=[
                "name",
                "unique_id",
                "state_topic",
                "command_topic",
                "value_template",
                "device",
                "availability",
                "device_class",
                "event_types",
            ],
        )
        logger.debug(f"publishing discovery about '{self.name}' to '{discovery_topic} with '{model}'")
        await mqtt.publish(
            discovery_topic,
            model,
            qos=1,
            retain=True,
        )


class MqttButtonDiscoveryDeviceClass(Enum):
    identify = "identify"
    restart = "restart"
    update = "update"


class MqttButtonDiscoveryPlatform(Enum):
    button = "button"


class MqttSensorDiscoveryPlatform(Enum):
    sensor = "sensor"


class MqttSensorDiscovery(MqttDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.sensor
    value_template: str | None = None
    json_attributes_topic: str | None = None
    platform: MqttSensorDiscoveryPlatform = MqttSensorDiscoveryPlatform.sensor


class MqttEventDiscoveryPlatform(Enum):
    event = "event"


class MqttEventDiscovery(MqttDiscovery):
    type: MqttDiscoveryType
    event_types: list[str] | None = None
    platform: MqttEventDiscoveryPlatform = MqttEventDiscoveryPlatform.event
    value_template: str | None = None


class MqttButtonDiscovery(MqttEventDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.event
    device_class: MqttDiscoveryDeviceClass | None = MqttDiscoveryDeviceClass.button


class MqttBinarySensorDiscovery(MqttEventDiscovery):
    type: MqttDiscoveryType = MqttDiscoveryType.binary_sensor


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
    device_class: MqttDiscoveryDeviceClass | None = None
    payload_lock: MqttLockDiscoveryState = MqttLockDiscoveryState.lock
    payload_unlock: MqttLockDiscoveryState = MqttLockDiscoveryState.unlock
    platform: MqttLockDiscoveryPlatform = MqttLockDiscoveryPlatform.lock
    state_jammed: MqttLockDiscoveryState = MqttLockDiscoveryState.jammed
    state_locked: MqttLockDiscoveryState = MqttLockDiscoveryState.locked
    state_unlocked: MqttLockDiscoveryState = MqttLockDiscoveryState.unlocked
