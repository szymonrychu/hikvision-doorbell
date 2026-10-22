import json
import xml.etree.ElementTree as ET
from enum import Enum

from pydantic import BaseModel, Field

from hikvision_doorbell.models.mqtt import MqttLockDiscoveryState


class CallButtonStates(Enum):
    released = "released"
    pressed = "pressed"
    busy = "busy"
    unknown = "unknown"


class CallInfo(Enum):
    idle = "idle"
    ring = "ring"
    calling = "onCall"
    error = "error"

    def to_mqtt_event_discovery_event_type(self) -> str:
        mapping = {
            CallInfo.idle: CallButtonStates.released,
            CallInfo.ring: CallButtonStates.pressed,
            CallInfo.calling: CallButtonStates.busy,
            CallInfo.error: CallButtonStates.unknown,
        }
        return json.dumps(
            {
                "event_type": mapping[self].value,
            }
        )


class DoorInfo(Enum):
    opened = "opened"
    closed = "closed"
    jammed = "jammed"

    def to_mqtt_lock_discovery_state(self) -> MqttLockDiscoveryState:
        mapping = {
            DoorInfo.opened: MqttLockDiscoveryState.unlock,
            DoorInfo.closed: MqttLockDiscoveryState.locked,
            DoorInfo.jammed: MqttLockDiscoveryState.jammed,
        }
        return mapping[self]


class DeviceInfo(BaseModel):
    device_name: str = Field(alias="deviceName")
    device_id: str = Field(alias="deviceID")
    device_description: str | None = Field(alias="deviceDescription", default=None)
    device_location: str | None = Field(alias="deviceLocation", default=None)
    system_contact: str | None = Field(alias="systemContact", default=None)
    model: str | None = Field(alias="model", default=None)
    serial_number: str | None = Field(alias="serialNumber", default=None)
    mac_address: str | None = Field(alias="macAddress", default=None)
    firmware_version: str | None = Field(alias="firmwareVersion", default=None)
    firmware_released_date: str | None = Field(alias="firmwareReleasedDate", default=None)
    boot_version: str | None = Field(alias="bootVersion", default=None)
    boot_released_date: str | None = Field(alias="bootReleasedDate", default=None)
    hardware_version: str | None = Field(alias="hardwareVersion", default=None)
    encoder_version: str | None = Field(alias="encoderVersion", default=None)
    encoder_released_date: str | None = Field(alias="encoderReleasedDate", default=None)
    device_type: str | None = Field(alias="deviceType", default=None)
    sub_device_type: str | None = Field(alias="subDeviceType", default=None)
    telecontrol_id: int | None = Field(alias="telecontrolID", default=None)
    support_beep: bool | None = Field(alias="supportBeep", default=None)
    support_video_loss: bool | None = Field(alias="supportVideoLoss", default=None)
    alarm_out_num: int | None = Field(alias="alarmOutNum", default=None)
    alarm_in_num: int | None = Field(alias="alarmInNum", default=None)
    rs485_num: int | None = Field(alias="RS485Num", default=None)
    customized_info: str | None = Field(alias="customizedInfo", default=None)

    @classmethod
    def from_xml(cls, xml_str: str) -> "DeviceInfo":
        root = ET.fromstring(xml_str)
        data = {}
        for child in root:
            tag = child.tag.split("}", 1)[-1]  # remove namespace
            data[tag] = child.text.strip() if child.text else None
        return cls(**data)
