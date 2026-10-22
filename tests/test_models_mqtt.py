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


def _base(**over):
    from hikvision_doorbell.models.mqtt import MqttDiscoveryDevice

    base = dict(
        availability=None,
        name="n",
        unique_id="u",
        device=MqttDiscoveryDevice(identifiers=["i"], manufacturer="m", model="x", name="d"),
        device_class=None,
    )
    base.update(over)
    return base


def _make(type_, **over):
    from pydantic import TypeAdapter  # noqa: F401

    from hikvision_doorbell.models import mqtt as m

    cls = {"lock": m.MqttLockDiscovery, "event": m.MqttButtonDiscovery}.get(type_, m.MqttDiscovery)
    return cls(**_base(type=m.MqttDiscoveryType(type_), **over))


def test_validator_rejects_lock_without_command_topic():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="command_topic"):
        _make("lock", state_topic="s")
    _make("lock", command_topic="c")


def test_validator_rejects_event_without_state_topic_or_event_types():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="state_topic"):
        _make("event", event_types=["ring"])
    with pytest.raises(ValidationError, match="event_types"):
        _make("event", state_topic="s", event_types=[])
    _make("event", state_topic="s", event_types=["ring"])


@pytest.mark.parametrize(
    "type_,cls_name",
    [("binary_sensor", "doorbell"), ("button", "occupancy"), ("lock", "lock"), ("event", "occupancy")],
)
def test_validator_rejects_invalid_device_class(type_, cls_name):
    from pydantic import ValidationError

    from hikvision_doorbell.models.mqtt import MqttDiscoveryDeviceClass

    with pytest.raises(ValidationError, match="invalid for"):
        _make(
            type_,
            device_class=MqttDiscoveryDeviceClass(cls_name),
            command_topic="c",
            state_topic="s",
            event_types=["ring"],
        )
