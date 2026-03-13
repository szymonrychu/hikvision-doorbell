"""Tests for hikvision_doorbell.helpers."""

import asyncio
from unittest.mock import MagicMock

import pytest

from hikvision_doorbell.helpers import (
    PerMessageRateLimitFilter,
    retry_async_yield,
    while_async_task_done,
)


class TestPerMessageRateLimitFilter:
    def test_same_message_throttled(self):
        f = PerMessageRateLimitFilter(min_interval_seconds=10)
        record = MagicMock()
        record.getMessage.return_value = "same message"
        assert f.filter(record) is True
        assert f.filter(record) is False
        assert f.filter(record) is False

    def test_different_message_allowed(self):
        f = PerMessageRateLimitFilter(min_interval_seconds=10)
        r1 = MagicMock()
        r1.getMessage.return_value = "message A"
        r2 = MagicMock()
        r2.getMessage.return_value = "message B"
        assert f.filter(r1) is True
        assert f.filter(r2) is True

    def test_same_message_allowed_after_interval(self):
        f = PerMessageRateLimitFilter(min_interval_seconds=0)
        record = MagicMock()
        record.getMessage.return_value = "msg"
        assert f.filter(record) is True
        assert f.filter(record) is True


class TestRetryAsyncYield:
    @pytest.mark.asyncio
    async def test_yields_on_success_immediately(self):
        calls = 0

        @retry_async_yield(attempts=3, delay=0.0)
        async def succeed():
            nonlocal calls
            calls += 1
            return "ok"

        results = []
        async for r in succeed():
            results.append(r)
        assert results == ["ok"]
        assert calls == 1

    @pytest.mark.asyncio
    async def test_yields_none_then_succeeds(self):
        calls = 0

        @retry_async_yield(attempts=3, delay=0.0)
        async def fail_twice():
            nonlocal calls
            calls += 1
            if calls < 3:
                return None
            return "ok"

        results = []
        async for r in fail_twice():
            results.append(r)
        assert results == [None, None, "ok"]
        assert calls == 3

    @pytest.mark.asyncio
    async def test_yields_none_n_times_on_repeated_failure(self):
        @retry_async_yield(attempts=3, delay=0.0)
        async def always_none():
            return None

        results = []
        async for r in always_none():
            results.append(r)
        assert results == [None, None, None]

    @pytest.mark.asyncio
    async def test_raises_last_exception_after_all_attempts(self):
        @retry_async_yield(
            attempts=3,
            delay=0.0,
            exceptions=(ValueError,),
        )
        async def always_raise():
            raise ValueError("err")

        with pytest.raises(ValueError, match="err"):
            async for _ in always_raise():
                pass

    @pytest.mark.asyncio
    async def test_raises_after_mixed_none_and_exception(self):
        calls = 0

        @retry_async_yield(attempts=3, delay=0.0, exceptions=(ValueError,))
        async def fail_none_then_raise():
            nonlocal calls
            calls += 1
            if calls < 2:
                return None
            raise ValueError("final")

        results = []
        with pytest.raises(ValueError, match="final"):
            async for r in fail_none_then_raise():
                results.append(r)
        assert results == [None, None, None]
        assert calls == 3

    @pytest.mark.asyncio
    async def test_does_not_catch_unlisted_exception(self):
        @retry_async_yield(attempts=2, delay=0.0, exceptions=(ValueError,))
        async def raise_type_error():
            raise TypeError("not caught")

        with pytest.raises(TypeError, match="not caught"):
            async for _ in raise_type_error():
                pass


class TestWhileAsyncTaskDone:
    @pytest.mark.asyncio
    async def test_stops_when_stop_event_set(self):
        stop = asyncio.Event()
        stop.set()

        @while_async_task_done(stop_event=stop, delay=0.0)
        async def never_run():
            return "x"

        results = []
        async for r in never_run():
            results.append(r)
        assert results == []

    @pytest.mark.asyncio
    async def test_yields_result_and_stops(self):
        stop = asyncio.Event()

        @while_async_task_done(stop_event=stop, delay=0.0)
        async def succeed():
            return "done"

        results = []
        async for r in succeed():
            results.append(r)
            break
        assert results == ["done"]

    @pytest.mark.asyncio
    async def test_yields_none_on_exception_then_continues(self):
        stop = asyncio.Event()
        calls = 0

        @while_async_task_done(stop_event=stop, delay=0.01, exceptions=(ValueError,))
        async def fail_once():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("oops")
            return "ok"

        results = []
        count = 0
        async for r in fail_once():
            results.append(r)
            if r == "ok":
                stop.set()
            count += 1
            if count > 5:
                stop.set()
                break
        assert "ok" in results
        assert calls == 2
