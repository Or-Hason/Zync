"""Endpoint tests for POST /api/jobs/scrape — extraction, validation, duplicates.

The pipeline always scores, so these tests supply an active resume and a
stubbed Gemini client; the pipeline-specific behaviours (blacklist, caching,
auto-reject, advice) live in test_jobs_pipeline.py.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests._job_pipeline import (
    FakeBlacklistStore,
    FakeGemini,
    FakeJobOllama,
    FakeJobSession,
    make_active_resume,
    make_score_result,
    pipeline_client,
)

_MAIN_HTML = (
    "<html><body><nav>menu</nav>"
    "<main><h1>Senior Python Engineer</h1>"
    "<p>Own the async FastAPI platform and PostgreSQL layer.</p></main>"
    "</body></html>"
)


@pytest.fixture
def session() -> FakeJobSession:
    fake = FakeJobSession()
    fake.active_resumes = [make_active_resume()]
    return fake


@pytest.fixture
def ollama() -> FakeJobOllama:
    return FakeJobOllama()


@pytest.fixture
def gemini() -> FakeGemini:
    return FakeGemini(result=make_score_result(78))


@pytest.fixture
def client(
    session: FakeJobSession, ollama: FakeJobOllama, gemini: FakeGemini
) -> Iterator[TestClient]:
    with pipeline_client(session, ollama, gemini, FakeBlacklistStore()) as test_client:
        yield test_client


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    async def _fake_fetch(_url: str) -> str:
        return html

    monkeypatch.setattr("app.api.jobs.fetch_html", _fake_fetch)


class TestScrapeFromUrl:
    """POST /api/jobs/scrape with a URL."""

    def test_valid_url_returns_201_structured(
        self, client: TestClient, ollama: FakeJobOllama, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_fetch(monkeypatch, _MAIN_HTML)
        response = client.post(
            "/api/jobs/scrape", json={"url": "https://jobs.example.com/123"}
        )

        assert response.status_code == 201
        body = response.json()
        assert body["company_name"] == "Acme Corp"
        assert body["job_title"] == "Senior Python Engineer"
        assert body["requirements"]["skills"] == ["Python", "FastAPI"]
        assert body["source_type"] == "manual"
        assert body["source_url"] == "https://jobs.example.com/123"
        # Ollama received the smart-extracted main content, not sidebar/nav.
        assert ollama.calls
        assert "Senior Python Engineer" in ollama.calls[0]
        assert "menu" not in ollama.calls[0]

    def test_oversized_url_content_rejected_422(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        huge = "word " * 200_000
        _patch_fetch(monkeypatch, f"<main>{huge}</main>")
        response = client.post(
            "/api/jobs/scrape", json={"url": "https://jobs.example.com/big"}
        )
        assert response.status_code == 422


class TestScrapeFromRawText:
    """POST /api/jobs/scrape with raw_text."""

    def test_raw_text_bypasses_scraping_201(
        self, client: TestClient, ollama: FakeJobOllama
    ) -> None:
        response = client.post(
            "/api/jobs/scrape",
            json={"raw_text": "Senior Python Engineer at Acme. Build APIs."},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["source_type"] == "manual"
        assert body["source_url"] is None
        assert ollama.calls[0].startswith("Senior Python Engineer at Acme")


class TestValidation:
    """Request validation and size guards."""

    def test_missing_both_sources_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/jobs/scrape", json={"force_score": True})
        assert response.status_code == 422

    def test_blank_raw_text_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/jobs/scrape", json={"raw_text": "   "})
        assert response.status_code == 422


class TestDuplicateDetection:
    """Endpoint wires duplicate detection into the persisted record."""

    def test_recent_similar_job_flags_duplicate(
        self, client: TestClient, session: FakeJobSession
    ) -> None:
        from tests._job_pipeline import ExistingRow

        session.existing_rows = [
            ExistingRow(
                "Senior Python Engineer",
                "Own the async FastAPI platform and PostgreSQL layer.",
                datetime.now(timezone.utc),
            )
        ]
        response = client.post(
            "/api/jobs/scrape",
            json={"raw_text": "duplicate of an existing recent posting"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["is_duplicate"] is True
        assert body["duplicate_chance"] >= 85

    def test_unique_job_not_flagged(
        self, client: TestClient, session: FakeJobSession
    ) -> None:
        session.existing_rows = []
        response = client.post(
            "/api/jobs/scrape", json={"raw_text": "a fresh unique job posting"}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["is_duplicate"] is False
        assert body["duplicate_chance"] == 0


class TestPrivacy:
    """PII / content must never be logged."""

    def test_job_description_not_logged(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            response = client.post(
                "/api/jobs/scrape", json={"raw_text": "some job text"}
            )
        assert response.status_code == 201
        # Only job_id and source_type are logged.
        assert "Own the async FastAPI platform" not in caplog.text
