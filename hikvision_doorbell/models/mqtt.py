import logging
from enum import Enum
from typing import List

from aiomqtt import Client
from pydantic import BaseModel

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
    identifiers: List[str]
    manufacturer: str
    model: str
    name: str


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

    async def publish_discovery(self, mqtt: Client, discovery_prefix: str):
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
    event_types: List[str] | None = None
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
