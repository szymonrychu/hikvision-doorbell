import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from hikvision_doorbell.models.mqtt import (
    LEGACY_DISCOVERY_TOPICS,
    VALID_DEVICE_CLASSES,
    MqttDiscovery,
)
from hikvision_doorbell.workers.doorbell import Doorbell

PREFIX = "homeassistant"


@pytest.fixture
def doorbell(monkeypatch):
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.HIK_HOST", "192.168.1.55")
    return Doorbell()


async def _published(discovery: MqttDiscovery):
    mqtt = MagicMock()
    mqtt.publish = AsyncMock()
    await discovery.publish_discovery(mqtt, PREFIX)
    topic, payload = mqtt.publish.call_args.args[:2]
    return topic, json.loads(payload)


@pytest.mark.asyncio
async def test_topic_matches_schema(doorbell):
    topic, payload = await _published(doorbell._lock_discovery)
    assert topic == f"{PREFIX}/lock/{doorbell._lock_discovery.unique_id}/config"
    assert payload["command_topic"]

    topic, payload = await _published(doorbell._ring_discovery)
    assert topic == f"{PREFIX}/event/{doorbell._ring_discovery.unique_id}/config"
    assert payload["state_topic"]
    assert payload["event_types"]


def test_event_payload_is_json(doorbell):
    event_types = doorbell._ring_discovery.event_types
    assert event_types and "unknown" not in event_types
    for payload in doorbell.ring_event_payloads():
        assert json.loads(payload)["event_type"] in event_types
    assert doorbell.ring_event_payload(None) is None
    assert doorbell.ring_event_payload("unknown") is None


@pytest.mark.asyncio
async def test_valid_device_classes(doorbell):
    for d in doorbell._discovery_list:
        _, payload = await _published(d)
        if "device_class" in payload:
            assert payload["device_class"] in VALID_DEVICE_CLASSES[d.type.value]
    assert "doorbell" not in VALID_DEVICE_CLASSES["binary_sensor"]
    assert "occupancy" not in VALID_DEVICE_CLASSES["button"]


def test_legacy_topics():
    assert sorted(LEGACY_DISCOVERY_TOPICS) == sorted(
        [
            "{prefix}/event/doorbell_state_lock/config",
            "{prefix}/lock/doorbell_state_sensor/config",
            "{prefix}/binary_sensor/hik_192_168_1_55_button/config",
            "{prefix}/button/doorbell_state_sensor/config",
        ]
    )
