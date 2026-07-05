"""Scheduler tests — TDD RED phase."""
from __future__ import annotations

import asyncio
import logging

import pytest

from quaestor.jobs import daily as daily_module


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_success(self, caplog):
        """daily.main is called via asyncio.to_thread; logs success."""
        caplog.set_level(logging.INFO)

        call_count = 0

        async def _fake_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            fn(*args, **kwargs)

        original_to_thread = asyncio.to_thread
        import quaestor.scheduler as scheduler_module

        scheduler_module.asyncio.to_thread = _fake_to_thread

        try:
            await scheduler_module._run_once()
        finally:
            scheduler_module.asyncio.to_thread = original_to_thread

        assert call_count == 1
        assert any("daily job ok" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_run_once_failure_logged_not_raised(self, caplog):
        """daily.main raises; exception is logged but NOT propagated (loop survives)."""
        caplog.set_level(logging.ERROR)

        def _raise(*args, **kwargs):
            raise RuntimeError("boom")

        import quaestor.scheduler as scheduler_module

        original_to_thread = asyncio.to_thread
        scheduler_module.asyncio.to_thread = _raise

        try:
            # Must NOT raise — exception should be swallowed
            await scheduler_module._run_once()
        finally:
            scheduler_module.asyncio.to_thread = original_to_thread

        assert any("daily job failed" in r.message for r in caplog.records)
        # log.exception captures exc_info in the traceback; check caplog.text for the full record
        assert "RuntimeError" in caplog.text
        assert "boom" in caplog.text


class TestRunForever:
    @pytest.mark.asyncio
    async def test_run_forever_runs_immediately_when_run_on_boot(self, monkeypatch):
        """RUN_ON_BOOT=1 → first call to _run_once happens BEFORE the first asyncio.sleep."""
        import quaestor.scheduler as scheduler_module

        calls: list[str] = []
        run_once_done = asyncio.Event()

        async def _mock_run_once():
            calls.append("_run_once")
            run_once_done.set()

        async def _mock_sleep(duration):
            calls.append(f"sleep({duration})")
            # Don't actually sleep — just record the call and let test cancel
            await asyncio.Event().wait()  # blocks forever until cancelled

        monkeypatch.setenv("RUN_ON_BOOT", "1")
        monkeypatch.setattr(scheduler_module, "_run_once", _mock_run_once)
        monkeypatch.setattr(scheduler_module.asyncio, "sleep", _mock_sleep)
        monkeypatch.setattr(scheduler_module, "INTERVAL_S", 86400)

        task = asyncio.create_task(scheduler_module.run_forever())

        # Wait for _run_once to complete, or timeout
        await asyncio.wait_for(run_once_done.wait(), timeout=2.0)

        # Now cancel — first action was definitely _run_once
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert calls[0] == "_run_once", f"Expected _run_once first, got {calls}"
        assert "sleep" in calls[1], f"Expected sleep second, got {calls}"

    @pytest.mark.asyncio
    async def test_run_forever_skips_initial_when_run_on_boot_0(
        self, monkeypatch
    ):
        """RUN_ON_BOOT=0 → first action is asyncio.sleep(INTERVAL_S), no immediate run."""
        import quaestor.scheduler as scheduler_module

        calls: list[str] = []

        async def _mock_run_once():
            calls.append("_run_once")

        async def _mock_sleep(duration):
            calls.append(f"sleep({duration})")
            raise asyncio.CancelledError("stop")

        monkeypatch.setenv("RUN_ON_BOOT", "0")
        monkeypatch.setattr(scheduler_module, "_run_once", _mock_run_once)
        monkeypatch.setattr(scheduler_module.asyncio, "sleep", _mock_sleep)
        monkeypatch.setattr(scheduler_module, "INTERVAL_S", 86400)

        task = asyncio.create_task(scheduler_module.run_forever())

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.5)

        # First action must be sleep, not _run_once
        assert calls[0].startswith("sleep"), f"Expected sleep first, got {calls}"
        assert "_run_once" not in calls, f"Unexpected _run_once call: {calls}"

    @pytest.mark.asyncio
    async def test_run_forever_cancellation_exits_cleanly(self, monkeypatch):
        """asyncio.CancelledError raised during asyncio.sleep propagates; loop exits (no second iteration)."""
        import quaestor.scheduler as scheduler_module

        iterations = 0

        async def _mock_run_once():
            nonlocal iterations
            iterations += 1

        sleep_count = 0

        async def _mock_sleep(duration):
            nonlocal sleep_count
            sleep_count += 1
            raise asyncio.CancelledError("shutdown")

        monkeypatch.setenv("RUN_ON_BOOT", "1")
        monkeypatch.setattr(scheduler_module, "_run_once", _mock_run_once)
        monkeypatch.setattr(scheduler_module.asyncio, "sleep", _mock_sleep)
        monkeypatch.setattr(scheduler_module, "INTERVAL_S", 86400)

        task = asyncio.create_task(scheduler_module.run_forever())

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.5)

        # Should have run once (on boot) and then cancelled during first sleep
        assert iterations == 1, f"Expected 1 iteration, got {iterations}"
        assert sleep_count == 1, f"Expected 1 sleep call, got {sleep_count}"
