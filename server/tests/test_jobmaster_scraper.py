"""Tests for the JobMaster scraper: URL building, link extraction, scan logic."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.scraper import jobmaster
from app.scraper.jobmaster import (
    apply_scan_caps,
    build_search_url,
    extract_job_links,
    run_scan,
    select_new_links,
)
from app.services.job_pipeline import (
    KIND_GEMINI_UNAVAILABLE,
    KIND_SCORED,
    PipelineOutcome,
)

_BASE = "https://www.jobmaster.co.il/"


class TestBuildSearchUrl:
    """build_search_url encodes the role and normalises the base URL."""

    def test_encodes_role(self) -> None:
        url = build_search_url(_BASE, "Backend Engineer")
        assert url == "https://www.jobmaster.co.il/jobs/?q=Backend+Engineer"

    def test_handles_missing_trailing_slash(self) -> None:
        url = build_search_url("https://www.jobmaster.co.il", "Python")
        assert url == "https://www.jobmaster.co.il/jobs/?q=Python"

    def test_encodes_non_ascii(self) -> None:
        url = build_search_url(_BASE, "מפתח")
        assert "jobs/?q=" in url
        assert " " not in url


class TestExtractJobLinks:
    """extract_job_links keeps only job anchors, resolved and de-duplicated."""

    def test_extracts_and_resolves_click_links(self) -> None:
        html = (
            "<a href='/code/kot/click.asp?i=11407'>Job A</a>"
            "<a href='/about'>About</a>"
            "<a href='https://www.jobmaster.co.il/code/kot/click.asp?i=222'>Job B</a>"
        )
        links = extract_job_links(html, _BASE)
        assert links == [
            "https://www.jobmaster.co.il/code/kot/click.asp?i=11407",
            "https://www.jobmaster.co.il/code/kot/click.asp?i=222",
        ]

    def test_deduplicates(self) -> None:
        html = (
            "<a href='/code/kot/click.asp?i=1'>x</a>"
            "<a href='/code/kot/click.asp?i=1'>x dup</a>"
        )
        assert extract_job_links(html, _BASE) == [
            "https://www.jobmaster.co.il/code/kot/click.asp?i=1"
        ]

    def test_no_job_links_returns_empty(self) -> None:
        html = "<a href='/about'>About</a><a href='/jobs/'>Jobs</a>"
        assert extract_job_links(html, _BASE) == []


class TestSelectNewLinks:
    """select_new_links drops URLs already in the DB."""

    def test_filters_known(self) -> None:
        scraped = ["u1", "u2", "u3"]
        assert select_new_links(scraped, {"u2"}) == ["u1", "u3"]

    def test_all_known_returns_empty(self) -> None:
        assert select_new_links(["u1"], {"u1"}) == []


class TestApplyScanCaps:
    """apply_scan_caps enforces first-run and per-scan ceilings."""

    def test_first_run_takes_last_initial_limit(self) -> None:
        links = ["a", "b", "c", "d", "e"]
        result = apply_scan_caps(
            links, is_first_run=True, initial_limit=3, max_per_scan=10
        )
        assert result == ["c", "d", "e"]

    def test_subsequent_run_applies_max_ceiling(self) -> None:
        links = [str(i) for i in range(50)]
        result = apply_scan_caps(
            links, is_first_run=False, initial_limit=3, max_per_scan=10
        )
        assert len(result) == 10
        assert result == [str(i) for i in range(10)]

    def test_first_run_then_max_ceiling(self) -> None:
        links = [str(i) for i in range(50)]
        result = apply_scan_caps(
            links, is_first_run=True, initial_limit=5, max_per_scan=2
        )
        # Last 5 selected by the first-run cap, then capped to 2 by the ceiling.
        assert result == ["45", "46"]


# ── run_scan orchestration ───────────────────────────────────────────────────


class _Result:
    def __init__(self, rows: list[Any], count: int | None = None) -> None:
        self._rows = rows
        self._count = count

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalar_one(self) -> int:
        return self._count or 0


class FakeScanSession:
    """Routes the three queries run_scan issues by selected-column name."""

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

    async def execute(self, stmt: Any) -> _Result:
        names = [d.get("name") for d in stmt.column_descriptions]
        if "Resume" in names:
            return _Result(self._active)
        if "source_url" in names:
            return _Result([SimpleNamespace(source_url=u) for u in self._known])
        return _Result([], count=self._count)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _resume(target_role: str | None = "Backend") -> Any:
    return SimpleNamespace(
        id=uuid4(),
        structured_data={"target_role": target_role} if target_role else {},
    )


def _patch_fetch_and_extract(monkeypatch: pytest.MonkeyPatch, search_html: str) -> None:
    async def _fake_fetch(url: str) -> str:
        # The search URL returns the listing; job pages return placeholder text.
        return search_html if "/jobs/?q=" in url else "job page text"

    monkeypatch.setattr(jobmaster, "fetch_html", _fake_fetch)
    monkeypatch.setattr(jobmaster, "extract_content", lambda html: html)


class _PipelineRecorder:
    """Records run_job_pipeline calls and returns scripted outcomes."""

    def __init__(self, kinds: list[str] | None = None) -> None:
        self.calls: list[dict] = []
        self._kinds = kinds or []

    async def __call__(self, **kwargs: Any) -> PipelineOutcome:
        self.calls.append(kwargs)
        idx = len(self.calls) - 1
        kind = self._kinds[idx] if idx < len(self._kinds) else KIND_SCORED
        return PipelineOutcome(kind=kind, job=SimpleNamespace(id=uuid4()))


@pytest.mark.asyncio
class TestRunScan:
    """Full-scan orchestration with the pipeline mocked."""

    async def test_aborts_without_active_resume(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = FakeScanSession(active_resumes=[], known_urls=[], source_count=0)
        recorder = _PipelineRecorder()
        monkeypatch.setattr(jobmaster, "run_job_pipeline", recorder)

        report = await run_scan(
            db=session, ollama=None, gemini=None, store=None,
            base_url=_BASE, initial_limit=3, max_per_scan=10,
        )
        assert report.aborted_reason == "no_active_resume"
        assert recorder.calls == []

    async def test_aborts_without_target_role(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = FakeScanSession(
            active_resumes=[_resume(target_role=None)], known_urls=[], source_count=0
        )
        recorder = _PipelineRecorder()
        monkeypatch.setattr(jobmaster, "run_job_pipeline", recorder)

        report = await run_scan(
            db=session, ollama=None, gemini=None, store=None,
            base_url=_BASE, initial_limit=3, max_per_scan=10,
        )
        assert report.aborted_reason == "no_target_role"
        assert recorder.calls == []

    async def test_first_run_caps_and_stamps_search_filters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        html = "".join(
            f"<a href='/code/kot/click.asp?i={i}'>j{i}</a>" for i in range(5)
        )
        _patch_fetch_and_extract(monkeypatch, html)
        recorder = _PipelineRecorder()
        monkeypatch.setattr(jobmaster, "run_job_pipeline", recorder)

        session = FakeScanSession(
            active_resumes=[_resume("Backend")], known_urls=[], source_count=0
        )
        report = await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url=_BASE, initial_limit=3, max_per_scan=10,
        )

        assert report.first_run is True
        assert report.discovered == 5
        assert report.processed == 3  # capped to initial_limit
        assert len(recorder.calls) == 3
        first = recorder.calls[0]
        assert first["source_type"] == "jobmaster"
        sf = first["search_filters"]
        assert sf["source"] == "jobmaster"
        assert sf["search_term"] == "Backend"
        assert sf["initial_run"] is True
        assert "scraped_at" in sf

    async def test_skips_known_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        html = (
            "<a href='/code/kot/click.asp?i=1'>a</a>"
            "<a href='/code/kot/click.asp?i=2'>b</a>"
        )
        _patch_fetch_and_extract(monkeypatch, html)
        recorder = _PipelineRecorder()
        monkeypatch.setattr(jobmaster, "run_job_pipeline", recorder)

        known = ["https://www.jobmaster.co.il/code/kot/click.asp?i=1"]
        session = FakeScanSession(
            active_resumes=[_resume("Backend")], known_urls=known, source_count=2
        )
        report = await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url=_BASE, initial_limit=3, max_per_scan=10,
        )
        assert report.new_links == 1
        assert len(recorder.calls) == 1
        assert recorder.calls[0]["source_url"].endswith("i=2")

    async def test_aborts_batch_on_gemini_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        html = "".join(
            f"<a href='/code/kot/click.asp?i={i}'>j{i}</a>" for i in range(3)
        )
        _patch_fetch_and_extract(monkeypatch, html)
        # Second job reports all models rate-limited -> scan must stop.
        recorder = _PipelineRecorder(kinds=[KIND_SCORED, KIND_GEMINI_UNAVAILABLE])
        monkeypatch.setattr(jobmaster, "run_job_pipeline", recorder)

        session = FakeScanSession(
            active_resumes=[_resume("Backend")], known_urls=[], source_count=5
        )
        report = await run_scan(
            db=session, ollama=object(), gemini=object(), store=object(),
            base_url=_BASE, initial_limit=3, max_per_scan=10,
        )
        # Two calls made (first scored, second hit the limit and broke the loop).
        assert len(recorder.calls) == 2
        assert report.processed == 1
