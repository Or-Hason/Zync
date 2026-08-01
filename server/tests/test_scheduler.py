"""Tests for the background scheduler: due-check logic and tick gating."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

# scan_tick's dependencies are resolved in app.background.tick — app.scheduler is
# only a re-export facade, so patching it would leave the real callables in place.
from app.background import tick
from app.scheduler import is_scan_due, scan_tick

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


class TestIsScanDue:
    """is_scan_due gates scans by elapsed time vs configured frequency."""

    def test_due_when_never_scanned(self) -> None:
        assert is_scan_due(None, frequency_hours=3, now=_NOW) is True

    def test_not_due_when_recent(self) -> None:
        last = (_NOW - timedelta(minutes=30)).isoformat()
        assert is_scan_due(last, frequency_hours=3, now=_NOW) is False

    def test_due_when_interval_elapsed(self) -> None:
        last = (_NOW - timedelta(hours=3, minutes=1)).isoformat()
        assert is_scan_due(last, frequency_hours=3, now=_NOW) is True

    def test_due_within_jitter_slack(self) -> None:
        # An hourly tick firing ~4 min early still counts the scan as due.
        last = (_NOW - timedelta(hours=1, minutes=-4)).isoformat()
        assert is_scan_due(last, frequency_hours=1, now=_NOW) is True

    def test_due_on_invalid_timestamp(self) -> None:
        assert is_scan_due("not-a-date", frequency_hours=3, now=_NOW) is True

    def test_naive_timestamp_treated_as_utc(self) -> None:
        last = (_NOW - timedelta(hours=6)).replace(tzinfo=None).isoformat()
        assert is_scan_due(last, frequency_hours=3, now=_NOW) is True


class FakeTickStore:
    """Store double for scan_tick gating tests.

    Mode A is used throughout: it is the frequency-only path these tests assert
    on, and it keeps ``reset_scheduler_timer`` out of the picture.
    """

    def __init__(self, *, enabled: bool, frequency: int, last: str | None) -> None:
        self._cfg = {
            "auto_scan_enabled": enabled,
            "scan_frequency_hours": frequency,
            "notification_score_threshold": 80,
            "scan_in_progress": False,
            "last_scan_at": None,
        }
        self._last = last
        self.set_last_calls: list[str] = []

    async def get_scan_settings(self) -> dict:
        return dict(self._cfg)

    async def get_notification_settings(self) -> dict:
        return {"notification_mode": "A"}

    async def get_last_scan_at(self) -> str | None:
        return self._last

    async def set_last_scan_at(self, iso_timestamp: str) -> None:
        self.set_last_calls.append(iso_timestamp)


class _FakeDB:
    async def commit(self) -> None:
        return None


class _FakeSessionFactory:
    """Async-context-manager factory yielding a fixed fake DB."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> Any:
        return self._db

    async def __aexit__(self, *_exc: Any) -> None:
        return None


def _wire(monkeypatch: pytest.MonkeyPatch, store: FakeTickStore) -> list[dict]:
    """Patch the tick module's deps; return a list capturing run_scan calls."""
    calls: list[dict] = []

    async def _fake_run_scan(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return None

    monkeypatch.setattr(tick, "AsyncSessionLocal", _FakeSessionFactory(_FakeDB()))
    monkeypatch.setattr(tick, "SettingsStore", lambda _db: store)
    monkeypatch.setattr(tick, "run_scan", _fake_run_scan)
    monkeypatch.setattr(tick, "get_gemini_client", lambda: object())
    monkeypatch.setattr(tick, "get_ollama_client", lambda: object())
    return calls


@pytest.fixture
def _no_swallowed_errors(caplog: pytest.LogCaptureFixture):
    """Fail the test if scan_tick's blanket except swallowed a real error.

    ``scan_tick`` deliberately catches everything so one bad tick cannot kill
    the loop. That also means a broken test wire-up looks identical to "the
    scan correctly did not run" — which is exactly how these tests rotted
    unnoticed. Asserting the log is empty makes the difference visible.
    """
    with caplog.at_level(logging.ERROR):
        yield
    assert "Background scan tick failed." not in caplog.text, caplog.text


@pytest.mark.asyncio
class TestScanTick:
    """scan_tick must respect auto_scan_enabled and the due-check."""

    async def test_disabled_does_not_scan(
        self, monkeypatch: pytest.MonkeyPatch, _no_swallowed_errors: None
    ) -> None:
        store = FakeTickStore(enabled=False, frequency=3, last=None)
        calls = _wire(monkeypatch, store)
        await scan_tick()
        assert calls == []
        assert store.set_last_calls == []

    async def test_enabled_and_due_runs_scan(
        self, monkeypatch: pytest.MonkeyPatch, _no_swallowed_errors: None
    ) -> None:
        store = FakeTickStore(enabled=True, frequency=3, last=None)
        calls = _wire(monkeypatch, store)
        await scan_tick()
        assert len(calls) == 1
        assert store.set_last_calls  # last_scan_at recorded after a run

    async def test_enabled_but_not_due_skips(
        self, monkeypatch: pytest.MonkeyPatch, _no_swallowed_errors: None
    ) -> None:
        recent = datetime.now(timezone.utc).isoformat()
        store = FakeTickStore(enabled=True, frequency=24, last=recent)
        calls = _wire(monkeypatch, store)
        await scan_tick()
        assert calls == []
        assert store.set_last_calls == []
