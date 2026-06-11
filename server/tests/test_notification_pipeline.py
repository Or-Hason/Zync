"""Tests for the SSE notification bus and the scraper notification hook."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.scraper import jobmaster
from app.scraper.jobmaster import run_scan
from app.services import notification_bus
from app.services.job_pipeline import KIND_GEMINI_UNAVAILABLE, KIND_SCORED, PipelineOutcome


# ── Notification bus unit tests ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestNotificationBus:
    """notification_bus: queue registration, event format, and cleanup."""

    async def test_emit_reaches_registered_client(self) -> None:
        q = notification_bus.add_client()
        try:
            await notification_bus.emit_job_match("job-abc", "Backend Dev", 88)
            msg = q.get_nowait()
            assert "job_match" in msg
            assert "job-abc" in msg
            assert "Backend Dev" in msg
            assert "88" in msg
            parsed = json.loads(msg.split("data: ", 1)[1])
            assert parsed["job_id"] == "job-abc"
            assert parsed["match_score"] == 88
        finally:
            notification_bus.remove_client(q)

    async def test_emit_is_noop_without_clients(self) -> None:
        # Ensure no clients from other tests leak; then emit should not raise.
        before = len(notification_bus._clients)
        await notification_bus.emit_job_match("x", "title", 90)
        assert len(notification_bus._clients) == before  # no side-effects

    async def test_event_reaches_multiple_clients(self) -> None:
        q1, q2 = notification_bus.add_client(), notification_bus.add_client()
        try:
            await notification_bus.emit_job_match("job-1", "Frontend Dev", 75)
            assert not q1.empty()
            assert not q2.empty()
        finally:
            notification_bus.remove_client(q1)
            notification_bus.remove_client(q2)

    async def test_remove_client_is_idempotent(self) -> None:
        q = notification_bus.add_client()
        notification_bus.remove_client(q)
        notification_bus.remove_client(q)  # must not raise

    async def test_stream_events_sends_ping_on_timeout(self) -> None:
        import app.services.notification_bus as bus_module

        original = bus_module._PING_INTERVAL_SECONDS
        bus_module._PING_INTERVAL_SECONDS = 0  # trigger immediately
        q = notification_bus.add_client()
        try:
            gen = notification_bus.stream_events(q)
            chunk = await gen.__anext__()
            assert chunk == ": ping\n\n"
        finally:
            bus_module._PING_INTERVAL_SECONDS = original
            await gen.aclose()


# ── Scraper notification hook integration tests ──────────────────────────────


class _FakeSessionWithFlush:
    """Minimal async DB session stub that supports flush."""

    def __init__(
        self,
        *,
        active_resumes: list[Any],
        known_urls: list[str],
        source_count: int,
    ) -> None:
        self._active = active_resumes
        self._known = known_urls
        self._count = source_count
        self.flushed = 0

    async def execute(self, stmt: Any) -> Any:
        class _R:
            def __init__(self, rows: list[Any], count: int = 0) -> None:
                self._rows, self._count = rows, count

            def scalars(self) -> "_R":
                return self

            def all(self) -> list[Any]:
                return list(self._rows)

            def scalar_one(self) -> int:
                return self._count

        names = [d.get("name") for d in stmt.column_descriptions]
        if "Resume" in names:
            return _R(self._active)
        if "source_url" in names:
            return _R([SimpleNamespace(source_url=u) for u in self._known])
        return _R([], count=self._count)

    async def flush(self) -> None:
        self.flushed += 1

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


def _resume(role: str = "Backend") -> Any:
    return SimpleNamespace(
        id=uuid4(),
        structured_data={"target_role": role},
    )


def _make_job(*, match_score: int | None = 85, notified_at: Any = None) -> Any:
    return SimpleNamespace(
        id=uuid4(),
        job_title="Test Job",
        match_score=match_score,
        notified_at=notified_at,
    )


def _patch_html(monkeypatch: pytest.MonkeyPatch, n_links: int = 1) -> None:
    html = "".join(
        f"<a href='/jobs/checknum.asp?key={i}'>j{i}</a>" for i in range(n_links)
    )

    async def _fetch(url: str) -> str:
        return html if "/jobs/?q=" in url else "job text"

    monkeypatch.setattr(jobmaster, "fetch_html", _fetch)
    monkeypatch.setattr(jobmaster, "extract_content", lambda h: h)


@pytest.mark.asyncio
class TestRunScanNotificationHook:
    """run_scan fires notifications when score meets threshold."""

    async def test_emits_when_score_meets_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_html(monkeypatch)
        job = _make_job(match_score=85)
        emits: list[dict] = []

        async def _fake_emit(job_id: str, job_title: str, match_score: int) -> None:
            emits.append({"job_id": job_id, "match_score": match_score})

        monkeypatch.setattr(notification_bus, "emit_job_match", _fake_emit)

        async def _pipeline(**kw: Any) -> PipelineOutcome:
            return PipelineOutcome(kind=KIND_SCORED, job=job)

        monkeypatch.setattr(jobmaster, "run_job_pipeline", _pipeline)
        session = _FakeSessionWithFlush(
            active_resumes=[_resume()], known_urls=[], source_count=0
        )

        await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url="https://www.jobmaster.co.il/",
            initial_limit=3, max_per_scan=10,
            notification_threshold=80,
        )

        assert len(emits) == 1
        assert emits[0]["match_score"] == 85
        assert job.notified_at is not None
        assert session.flushed >= 1

    async def test_no_emit_below_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_html(monkeypatch)
        job = _make_job(match_score=70)
        emits: list[dict] = []

        async def _fake_emit(**kw: Any) -> None:
            emits.append(kw)

        monkeypatch.setattr(notification_bus, "emit_job_match", _fake_emit)

        async def _pipeline(**kw: Any) -> PipelineOutcome:
            return PipelineOutcome(kind=KIND_SCORED, job=job)

        monkeypatch.setattr(jobmaster, "run_job_pipeline", _pipeline)
        session = _FakeSessionWithFlush(
            active_resumes=[_resume()], known_urls=[], source_count=0
        )

        await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url="https://www.jobmaster.co.il/",
            initial_limit=3, max_per_scan=10,
            notification_threshold=80,
        )

        assert emits == []
        assert job.notified_at is None

    async def test_no_emit_when_already_notified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from datetime import datetime, timezone

        _patch_html(monkeypatch)
        already_stamped = datetime.now(timezone.utc)
        job = _make_job(match_score=90, notified_at=already_stamped)
        emits: list[dict] = []

        async def _fake_emit(**kw: Any) -> None:
            emits.append(kw)

        monkeypatch.setattr(notification_bus, "emit_job_match", _fake_emit)

        async def _pipeline(**kw: Any) -> PipelineOutcome:
            return PipelineOutcome(kind=KIND_SCORED, job=job)

        monkeypatch.setattr(jobmaster, "run_job_pipeline", _pipeline)
        session = _FakeSessionWithFlush(
            active_resumes=[_resume()], known_urls=[], source_count=0
        )

        await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url="https://www.jobmaster.co.il/",
            initial_limit=3, max_per_scan=10,
            notification_threshold=80,
        )

        assert emits == []  # already notified — no re-emission

    async def test_no_emit_when_threshold_is_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default threshold=None must never touch notification_bus."""
        _patch_html(monkeypatch)
        job = _make_job(match_score=100)
        emits: list[dict] = []

        async def _fake_emit(**kw: Any) -> None:
            emits.append(kw)

        monkeypatch.setattr(notification_bus, "emit_job_match", _fake_emit)

        async def _pipeline(**kw: Any) -> PipelineOutcome:
            return PipelineOutcome(kind=KIND_SCORED, job=job)

        monkeypatch.setattr(jobmaster, "run_job_pipeline", _pipeline)
        session = _FakeSessionWithFlush(
            active_resumes=[_resume()], known_urls=[], source_count=0
        )

        await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url="https://www.jobmaster.co.il/",
            initial_limit=3, max_per_scan=10,
            # notification_threshold not passed — defaults to None
        )

        assert emits == []


# ── SSE endpoint content-type test ───────────────────────────────────────────


def test_sse_endpoint_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/notifications/stream must return text/event-stream."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.notifications import router
    from app.services import notification_bus

    async def _finite(_q: Any) -> Any:
        yield ": ping\n\n"

    monkeypatch.setattr(notification_bus, "stream_events", _finite)

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        resp = client.get("/notifications/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
