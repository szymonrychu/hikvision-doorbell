"""Tests for hikvision_doorbell.workers.doorbell."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hikvision_doorbell.models.hikvision import CallInfo, DeviceInfo, DoorInfo
from hikvision_doorbell.models.mqtt import MqttMessageAvailabilityPayload
from hikvision_doorbell.workers.doorbell import Doorbell
from tests.conftest import SAMPLE_DEVICE_INFO_XML


@pytest.fixture
def doorbell(monkeypatch):
    """Create a Doorbell instance with mocked settings."""
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.HIK_HOST", "192.168.1.100")
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.HIK_HTTPS", False)
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.HIK_USERNAME", "user")
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.HIK_PASSWORD", "pass")
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.MQTT_HOST", "localhost")
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.MQTT_PORT", 1883)
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.DOOR_RELAY_ID", 1)
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.DEVICE_CALL_RETRY_MAX_COUNT", 2)
    monkeypatch.setattr("hikvision_doorbell.workers.doorbell.settings.DEVICE_CALL_RETRY_DELAY", 0.01)
    return Doorbell()


class TestDoorbellUrl:
    def test_url_adds_slash_prefix(self, doorbell):
        assert doorbell._url("/path") == "http://192.168.1.100/path"

    def test_url_strips_leading_slash(self, doorbell):
        assert doorbell._url("path") == "http://192.168.1.100/path"


class TestDoorbellParseCallStatus:
    def test_parse_idle(self, doorbell):
        assert doorbell._parse_call_status({"CallStatus": {"status": "idle"}}) == CallInfo.idle

    def test_parse_ring(self, doorbell):
        assert doorbell._parse_call_status({"CallStatus": {"status": "ring"}}) == CallInfo.ring

    def test_parse_onCall(self, doorbell):
        assert doorbell._parse_call_status({"CallStatus": {"status": "onCall"}}) == CallInfo.calling

    def test_parse_error(self, doorbell):
        assert doorbell._parse_call_status({"CallStatus": {"status": "error"}}) == CallInfo.error

    def test_parse_missing_status_returns_none(self, doorbell):
        assert doorbell._parse_call_status({"CallStatus": {}}) is None

    def test_parse_missing_call_status_returns_none(self, doorbell):
        assert doorbell._parse_call_status({}) is None

    def test_parse_unknown_status_returns_none(self, doorbell):
        assert doorbell._parse_call_status({"CallStatus": {"status": "unknown_firmware_value"}}) is None


class TestDoorbellGetters:
    @pytest.mark.asyncio
    async def test_get_device_info_returns_cached(self, doorbell):
        info = DeviceInfo(deviceName="X", deviceID="Y")
        doorbell._device_info = info
        assert await doorbell.get_device_info() is info

    @pytest.mark.asyncio
    async def test_get_device_info_none_when_empty(self, doorbell):
        doorbell._device_info = None
        assert await doorbell.get_device_info() is None

    @pytest.mark.asyncio
    async def test_get_call_info_returns_cached(self, doorbell):
        doorbell._call_info = CallInfo.ring
        assert await doorbell.get_call_info() == CallInfo.ring

    @pytest.mark.asyncio
    async def test_device_healthy(self, doorbell):
        doorbell._device_healthy = True
        assert await doorbell.device_healthy() is True
        doorbell._device_healthy = False
        assert await doorbell.device_healthy() is False


class TestDoorbellOpenCloseDoors:
    @pytest.mark.asyncio
    async def test_returns_jammed_when_client_none(self, doorbell):
        doorbell._client = None
        result = await doorbell.open_close_doors(True)
        assert result == DoorInfo.jammed

    @pytest.mark.asyncio
    async def test_returns_opened_on_success(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        result = await doorbell.open_close_doors(True)
        assert result == DoorInfo.opened

    @pytest.mark.asyncio
    async def test_returns_closed_on_success(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        result = await doorbell.open_close_doors(False)
        assert result == DoorInfo.closed

    @pytest.mark.asyncio
    async def test_returns_jammed_on_all_failures(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        result = await doorbell.open_close_doors(True)
        assert result == DoorInfo.jammed


class TestDoorbellGetDeviceInfo:
    @pytest.mark.asyncio
    async def test_returns_device_info_on_success(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = SAMPLE_DEVICE_INFO_XML.encode("utf-8")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        results = []
        async for r in doorbell._get_device_info(mock_client):
            results.append(r)
        assert len(results) == 1
        assert isinstance(results[0], DeviceInfo)
        assert results[0].device_name == "DS-KV6113-WPE1"

    @pytest.mark.asyncio
    async def test_returns_none_on_non_2xx(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        results = []
        async for r in doorbell._get_device_info(mock_client):
            results.append(r)
        assert len(results) >= 1
        assert all(r is None for r in results)

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_xml(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"not xml"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        results = []
        async for r in doorbell._get_device_info(mock_client):
            results.append(r)
        assert len(results) >= 1
        assert results[-1] is None or isinstance(results[-1], DeviceInfo) is False


class TestDoorbellGetCallStatus:
    @pytest.mark.asyncio
    async def test_returns_call_info_on_valid_json(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"CallStatus": {"status": "idle"}}'
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        results = []
        async for r in doorbell._get_call_status(mock_client):
            results.append(r)
        assert len(results) == 1
        assert results[0] == CallInfo.idle

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self, doorbell):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"not json"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        results = []
        async for r in doorbell._get_call_status(mock_client):
            results.append(r)
        assert len(results) >= 1
        assert all(r is None for r in results)


class TestDoorbellPublish:
    @pytest.mark.asyncio
    async def test_publish_if_changed_publishes_when_value_differs(self, doorbell):
        mock_publish = AsyncMock()
        mock_mqtt = MagicMock()
        mock_mqtt.publish = mock_publish
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_mqtt
        mock_cm.__aexit__.return_value = None

        with patch(
            "hikvision_doorbell.workers.doorbell.Client",
            return_value=mock_cm,
        ):
            await doorbell.publish_if_changed("topic/state", "online")
        mock_publish.assert_called_once()
        assert doorbell.state_cache.get("topic/state") == "online"

    @pytest.mark.asyncio
    async def test_publish_if_changed_skips_when_value_unchanged(self, doorbell):
        doorbell.state_cache["topic/state"] = "online"
        mock_publish = AsyncMock()

        with patch(
            "hikvision_doorbell.workers.doorbell.Client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=MagicMock(publish=mock_publish))),
        ):
            await doorbell.publish_if_changed("topic/state", "online")
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_discovery(self, doorbell):
        mock_mqtt = MagicMock()
        mock_mqtt.publish = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_mqtt
        mock_cm.__aexit__.return_value = None

        with patch(
            "hikvision_doorbell.workers.doorbell.Client",
            return_value=mock_cm,
        ):
            await doorbell.publish_discovery()
        assert mock_mqtt.publish.called

    @pytest.mark.asyncio
    async def test_publish_availability_online(self, doorbell):
        with patch.object(doorbell, "publish_if_changed", AsyncMock()) as mock_pub:
            await doorbell.publish_availability(True)
            assert mock_pub.call_count >= 1
            calls = [str(c) for c in mock_pub.call_args_list]
            assert any(MqttMessageAvailabilityPayload.payload_available.value in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_publish_availability_offline_sets_reseted(self, doorbell):
        doorbell._reseted_availability = False
        with patch.object(doorbell, "publish_if_changed", AsyncMock()):
            await doorbell.publish_availability(False)
        assert doorbell._reseted_availability is True


class TestDoorbellTasks:
    @pytest.mark.asyncio
    async def test_tasks_returns_list_of_tasks(self, doorbell):
        stop = __import__("asyncio").Event()
        tasks = doorbell.tasks(stop)
        assert len(tasks) == 4
        for t in tasks:
            assert hasattr(t, "cancel")
        stop.set()
        for t in tasks:
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass


class TestDoorbellRefreshClient:
    @pytest.mark.asyncio
    async def test_refresh_client_closes_old_client(self, doorbell):
        with patch(
            "hikvision_doorbell.workers.doorbell.REFRESH_SLEEP_TIME",
            0.05,
        ):
            stop = __import__("asyncio").Event()
            mock_old = AsyncMock()
            mock_old.aclose = AsyncMock()
            doorbell._client = mock_old
            t = __import__("asyncio").create_task(doorbell.refresh_client(stop))
            await __import__("asyncio").sleep(0.15)
            stop.set()
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass
        mock_old.aclose.assert_called_once()


class TestDoorbellHandleDeviceInfos:
    @pytest.mark.asyncio
    async def test_handle_device_infos_iterates_until_stop(self, doorbell):
        stop = __import__("asyncio").Event()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = SAMPLE_DEVICE_INFO_XML.encode("utf-8")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        with patch.object(doorbell, "publish_availability", AsyncMock()):
            with patch.object(doorbell, "publish_if_changed", AsyncMock()):
                t = __import__("asyncio").create_task(doorbell.handle_device_infos(stop))
                await __import__("asyncio").sleep(0.4)
                stop.set()
                await __import__("asyncio").sleep(0.2)
                t.cancel()
                try:
                    await t
                except __import__("asyncio").CancelledError:
                    pass
        assert doorbell._device_info is not None or not doorbell._device_healthy

    @pytest.mark.asyncio
    async def test_handle_device_infos_waits_for_client(self, doorbell):
        stop = __import__("asyncio").Event()
        doorbell._client = None

        async def set_stop():
            await __import__("asyncio").sleep(0.2)
            stop.set()

        __import__("asyncio").create_task(set_stop())
        t = __import__("asyncio").create_task(doorbell.handle_device_infos(stop))
        await __import__("asyncio").sleep(0.4)
        t.cancel()
        try:
            await t
        except __import__("asyncio").CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_handle_device_infos_exception_marks_unhealthy(self, doorbell):
        stop = __import__("asyncio").Event()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection lost"))
        doorbell._client = mock_client

        with patch.object(doorbell, "publish_availability", AsyncMock()):
            t = __import__("asyncio").create_task(doorbell.handle_device_infos(stop))
            await __import__("asyncio").sleep(0.3)
            stop.set()
            await __import__("asyncio").sleep(0.2)
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass
        assert doorbell._device_healthy is False


class TestDoorbellHandleCallStatuses:
    @pytest.mark.asyncio
    async def test_handle_call_statuses_publishes_idle(self, doorbell):
        stop = __import__("asyncio").Event()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"CallStatus": {"status": "idle"}}'
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        with patch.object(doorbell, "publish_if_changed", AsyncMock()) as mock_pub:
            t = __import__("asyncio").create_task(doorbell.handle_call_statuses(stop))
            await __import__("asyncio").sleep(0.3)
            stop.set()
            await __import__("asyncio").sleep(0.2)
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass
            assert mock_pub.called

    @pytest.mark.asyncio
    async def test_handle_call_statuses_publishes_ring_press_and_release(self, doorbell):
        stop = __import__("asyncio").Event()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"CallStatus": {"status": "ring"}}'
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        with patch.object(doorbell, "publish_if_changed", AsyncMock()) as mock_pub:
            t = __import__("asyncio").create_task(doorbell.handle_call_statuses(stop))
            await __import__("asyncio").sleep(1.5)
            stop.set()
            await __import__("asyncio").sleep(0.2)
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass
            calls = [str(c) for c in mock_pub.call_args_list]
            assert any("pressed" in c for c in calls)
            assert any("released" in c for c in calls)

    @pytest.mark.asyncio
    async def test_handle_call_statuses_waits_for_client(self, doorbell):
        stop = __import__("asyncio").Event()
        doorbell._client = None

        async def set_stop():
            await __import__("asyncio").sleep(0.2)
            stop.set()

        __import__("asyncio").create_task(set_stop())
        t = __import__("asyncio").create_task(doorbell.handle_call_statuses(stop))
        await __import__("asyncio").sleep(0.4)
        t.cancel()
        try:
            await t
        except __import__("asyncio").CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_handle_call_statuses_exception_publishes_unknown(self, doorbell):
        stop = __import__("asyncio").Event()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        doorbell._client = mock_client

        with patch.object(doorbell, "publish_if_changed", AsyncMock()) as mock_pub:
            t = __import__("asyncio").create_task(doorbell.handle_call_statuses(stop))
            await __import__("asyncio").sleep(0.3)
            stop.set()
            await __import__("asyncio").sleep(0.2)
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass
            calls = [str(c) for c in mock_pub.call_args_list]
            assert any("unknown" in c for c in calls)

    @pytest.mark.asyncio
    async def test_handle_call_statuses_publishes_unknown_on_none_attempt(self, doorbell):
        stop = __import__("asyncio").Event()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        doorbell._client = mock_client

        with patch.object(doorbell, "publish_if_changed", AsyncMock()) as mock_pub:
            t = __import__("asyncio").create_task(doorbell.handle_call_statuses(stop))
            await __import__("asyncio").sleep(0.3)
            stop.set()
            await __import__("asyncio").sleep(0.2)
            t.cancel()
            try:
                await t
            except __import__("asyncio").CancelledError:
                pass
            calls = [str(c) for c in mock_pub.call_args_list]
            assert any("unknown" in c for c in calls)


class TestDoorbellPublishIfChangedError:
    @pytest.mark.asyncio
    async def test_publish_if_changed_logs_on_mqtt_error(self, doorbell):
        mock_cm = AsyncMock()
        mock_cm.__aenter__.side_effect = Exception("mqtt down")

        with patch(
            "hikvision_doorbell.workers.doorbell.Client",
            return_value=mock_cm,
        ):
            await doorbell.publish_if_changed("topic/test", "value")
        assert doorbell.state_cache.get("topic/test") == "value"

    @pytest.mark.asyncio
    async def test_publish_discovery_logs_on_mqtt_error(self, doorbell):
        mock_cm = AsyncMock()
        mock_cm.__aenter__.side_effect = Exception("mqtt down")

        with patch(
            "hikvision_doorbell.workers.doorbell.Client",
            return_value=mock_cm,
        ):
            await doorbell.publish_discovery()
