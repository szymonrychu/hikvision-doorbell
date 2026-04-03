"""Tests for hikvision_doorbell.settings."""

from unittest.mock import MagicMock

from hikvision_doorbell.settings import EndpointFilter


class TestEndpointFilter:
    def test_filters_liveness_path_with_tuple_args(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = ("127.0.0.1", "GET", "/healthz/live", 200, "-")
        assert f.filter(record) is False

    def test_filters_readiness_path_with_tuple_args(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = ("127.0.0.1", "GET", "/healthz/ready", 200, "-")
        assert f.filter(record) is False

    def test_allows_other_paths_with_tuple_args(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = ("127.0.0.1", "GET", "/api/data", 200, "-")
        assert f.filter(record) is True

    def test_allows_when_args_is_dict_with_other_path(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = {"path": "/api/data"}
        assert f.filter(record) is True

    def test_filters_when_args_is_dict_with_health_path(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = {"path": "/healthz/live"}
        assert f.filter(record) is False

    def test_allows_when_args_is_none(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = None
        assert f.filter(record) is True

    def test_allows_when_args_is_short_tuple(self):
        f = EndpointFilter()
        record = MagicMock()
        record.args = ("only", "two")
        assert f.filter(record) is True
