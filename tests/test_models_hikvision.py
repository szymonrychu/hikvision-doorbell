"""Tests for hikvision_doorbell.models.hikvision."""

import json
import xml.etree.ElementTree as ET

import pytest

from hikvision_doorbell.models.hikvision import (
    CallButtonStates,
    CallInfo,
    DeviceInfo,
    DoorInfo,
)
from hikvision_doorbell.models.mqtt import MqttLockDiscoveryState
from tests.conftest import SAMPLE_DEVICE_INFO_XML


class TestCallButtonStates:
    def test_values(self):
        assert CallButtonStates.released.value == "released"
        assert CallButtonStates.pressed.value == "pressed"
        assert CallButtonStates.busy.value == "busy"
        assert CallButtonStates.unknown.value == "unknown"


class TestCallInfo:
    def test_values(self):
        assert CallInfo.idle.value == "idle"
        assert CallInfo.ring.value == "ring"
        assert CallInfo.calling.value == "onCall"
        assert CallInfo.error.value == "error"

    def test_to_mqtt_event_discovery_event_type_idle(self):
        s = CallInfo.idle.to_mqtt_event_discovery_event_type()
        data = json.loads(s)
        assert data["event_type"] == "released"

    def test_to_mqtt_event_discovery_event_type_ring(self):
        s = CallInfo.ring.to_mqtt_event_discovery_event_type()
        data = json.loads(s)
        assert data["event_type"] == "pressed"

    def test_to_mqtt_event_discovery_event_type_calling(self):
        s = CallInfo.calling.to_mqtt_event_discovery_event_type()
        data = json.loads(s)
        assert data["event_type"] == "busy"

    def test_to_mqtt_event_discovery_event_type_error(self):
        s = CallInfo.error.to_mqtt_event_discovery_event_type()
        data = json.loads(s)
        assert data["event_type"] == "unknown"


class TestDoorInfo:
    def test_values(self):
        assert DoorInfo.opened.value == "opened"
        assert DoorInfo.closed.value == "closed"
        assert DoorInfo.jammed.value == "jammed"

    def test_to_mqtt_lock_discovery_state_opened(self):
        assert DoorInfo.opened.to_mqtt_lock_discovery_state() == MqttLockDiscoveryState.unlock

    def test_to_mqtt_lock_discovery_state_closed(self):
        assert DoorInfo.closed.to_mqtt_lock_discovery_state() == MqttLockDiscoveryState.locked

    def test_to_mqtt_lock_discovery_state_jammed(self):
        assert DoorInfo.jammed.to_mqtt_lock_discovery_state() == MqttLockDiscoveryState.jammed


class TestDeviceInfo:
    def test_from_xml_valid(self):
        info = DeviceInfo.from_xml(SAMPLE_DEVICE_INFO_XML)
        assert info.device_name == "DS-KV6113-WPE1"
        assert info.device_id == "12345"
        assert info.device_description == "IP Video Intercom"
        assert info.model == "DS-KV6113-WPE1(C)"

    def test_from_xml_with_namespace(self):
        xml = """<?xml version="1.0"?>
<DeviceInfo xmlns="urn:whatever">
  <deviceName>Test</deviceName>
  <deviceID>99</deviceID>
</DeviceInfo>
"""
        info = DeviceInfo.from_xml(xml)
        assert info.device_name == "Test"
        assert info.device_id == "99"

    def test_from_xml_invalid_raises(self):
        with pytest.raises(ET.ParseError):
            DeviceInfo.from_xml("not valid xml <<<")
