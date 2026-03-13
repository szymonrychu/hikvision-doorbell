"""Tests for hikvision_doorbell.app."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from hikvision_doorbell.app import app


@pytest.fixture
def mock_doorbell_tasks():
    """Mock doorbell.tasks and publish_discovery to avoid real MQTT/HTTP."""

    async def quick_task():
        return

    def tasks(stop_event):
        t = __import__("asyncio").create_task(quick_task())
        return [t]

    with patch("hikvision_doorbell.app.doorbell") as mock_db:
        mock_db.tasks = tasks
        mock_db.publish_discovery = AsyncMock()
        yield mock_db


def test_liveness_returns_200():
    client = TestClient(app)
    resp = client.get("/healthz/live")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_readiness_returns_200():
    client = TestClient(app)
    resp = client.get("/healthz/ready")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_lifespan_starts_and_stops(mock_doorbell_tasks):
    """Test that app lifespan starts and stops without error."""
    client = TestClient(app)
    # TestClient triggers lifespan on first request; verify no exception
    resp = client.get("/healthz/live")
    assert resp.status_code == 200


def test_serve_calls_uvicorn():
    """Test that main.serve() invokes uvicorn.run with correct args."""
    from hikvision_doorbell.main import serve

    with patch("hikvision_doorbell.main.uvicorn.run") as mock_run:
        serve()
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == "hikvision_doorbell.app:app"
        assert "host" in call_args[1]
        assert "port" in call_args[1]


@pytest.mark.asyncio
async def test_lifespan_yield(mock_doorbell_tasks):
    """Test lifespan context manager runs startup and shutdown."""
    from hikvision_doorbell.app import app, lifespan

    async with lifespan(app):
        pass
