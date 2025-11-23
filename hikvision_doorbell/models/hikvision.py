import json
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Optional

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
    device_description: Optional[str] = Field(alias="deviceDescription", default=None)
    device_location: Optional[str] = Field(alias="deviceLocation", default=None)
    system_contact: Optional[str] = Field(alias="systemContact", default=None)
    model: Optional[str] = Field(alias="model", default=None)
    serial_number: Optional[str] = Field(alias="serialNumber", default=None)
    mac_address: Optional[str] = Field(alias="macAddress", default=None)
    firmware_version: Optional[str] = Field(alias="firmwareVersion", default=None)
    firmware_released_date: Optional[str] = Field(alias="firmwareReleasedDate", default=None)
    boot_version: Optional[str] = Field(alias="bootVersion", default=None)
    boot_released_date: Optional[str] = Field(alias="bootReleasedDate", default=None)
    hardware_version: Optional[str] = Field(alias="hardwareVersion", default=None)
    encoder_version: Optional[str] = Field(alias="encoderVersion", default=None)
    encoder_released_date: Optional[str] = Field(alias="encoderReleasedDate", default=None)
    device_type: Optional[str] = Field(alias="deviceType", default=None)
    sub_device_type: Optional[str] = Field(alias="subDeviceType", default=None)
    telecontrol_id: Optional[int] = Field(alias="telecontrolID", default=None)
    support_beep: Optional[bool] = Field(alias="supportBeep", default=None)
    support_video_loss: Optional[bool] = Field(alias="supportVideoLoss", default=None)
    alarm_out_num: Optional[int] = Field(alias="alarmOutNum", default=None)
    alarm_in_num: Optional[int] = Field(alias="alarmInNum", default=None)
    rs485_num: Optional[int] = Field(alias="RS485Num", default=None)
    customized_info: Optional[str] = Field(alias="customizedInfo", default=None)

    @classmethod
    def from_xml(cls, xml_str: str) -> "DeviceInfo":
        root = ET.fromstring(xml_str)
        data = {}
        for child in root:
            tag = child.tag.split("}", 1)[-1]  # remove namespace
            data[tag] = child.text.strip() if child.text else None
        return cls(**data)
