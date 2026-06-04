"""Endpoint tests for POST /api/jobs/scrape with mocked boundaries."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.job import Job
from app.services.ollama_client import get_ollama_client

_SAMPLE_JOB_RAW: dict[str, Any] = {
    "company_name": "Acme Corp",
    "job_title": "Senior Python Engineer",
    "company_description": "We ship logistics software.",
    "job_description": "Own the async FastAPI platform and PostgreSQL layer.",
    "requirements": {
        "skills": ["Python", "FastAPI"],
        "years_of_experience": 5,
        "education": "B.Sc.",
        "other": [],
    },
    "published_at": "2026-05-01",
}

_MAIN_HTML = (
    "<html><body><nav>menu</nav>"
    "<main><h1>Senior Python Engineer</h1>"
    "<p>Own the async FastAPI platform and PostgreSQL layer.</p></main>"
    "</body></html>"
)


class _Row:
    """Column-projection row stand-in for the duplicate-scan query."""

    def __init__(self, title: str, description: str, created_at: datetime) -> None:
        self.job_title = title
        self.job_description = description
        self.created_at = created_at


class _Result:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def all(self) -> list[_Row]:
        return list(self._rows)


class FakeJobSession:
    """In-memory async session double for the jobs endpoint."""

    def __init__(self) -> None:
        self.added: list[Job] = []
        self.existing_rows: list[_Row] = []

    def add(self, obj: Job) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            _ensure_created_at(obj)

    async def refresh(self, obj: Job) -> None:
        _ensure_created_at(obj)

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self.existing_rows)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _ensure_created_at(obj: Job) -> None:
    if getattr(obj, "created_at", None) is None:
        obj.created_at = datetime.now(timezone.utc)


class FakeJobOllama:
    """Stub Ollama client returning a preset job payload and recording input."""

    def __init__(self) -> None:
        self.payload: dict[str, Any] = dict(_SAMPLE_JOB_RAW)
        self.calls: list[str] = []

    async def parse_job(self, raw_text: str) -> dict[str, Any]:
        self.calls.append(raw_text)
        return self.payload


@pytest.fixture
def fake_session() -> FakeJobSession:
    return FakeJobSession()


@pytest.fixture
def fake_ollama() -> FakeJobOllama:
    return FakeJobOllama()


@pytest.fixture
def client(
    fake_session: FakeJobSession,
    fake_ollama: FakeJobOllama,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Yield a TestClient with DB and Ollama mocked; fetch is patched per-test."""

    async def _override_get_db() -> AsyncIterator[FakeJobSession]:
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_ollama_client] = lambda: fake_ollama

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    async def _fake_fetch(_url: str) -> str:
        return html

    monkeypatch.setattr("app.api.jobs.fetch_html", _fake_fetch)


class TestScrapeFromUrl:
    """POST /api/jobs/scrape with a URL."""

    def test_valid_url_returns_201_structured(
        self,
        client: TestClient,
        fake_ollama: FakeJobOllama,
        monkeypatch: pytest.MonkeyPatch,
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
        assert body["status"] == "not_applied"
        assert body["source_url"] == "https://jobs.example.com/123"
        # Ollama received the smart-extracted main content, not sidebar/nav.
        assert fake_ollama.calls
        assert "Senior Python Engineer" in fake_ollama.calls[0]
        assert "menu" not in fake_ollama.calls[0]

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
        self, client: TestClient, fake_ollama: FakeJobOllama
    ) -> None:
        response = client.post(
            "/api/jobs/scrape",
            json={"raw_text": "Senior Python Engineer at Acme. Build APIs."},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["source_type"] == "manual"
        assert body["source_url"] is None
        assert fake_ollama.calls[0].startswith("Senior Python Engineer at Acme")


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
        self, client: TestClient, fake_session: FakeJobSession
    ) -> None:
        fake_session.existing_rows = [
            _Row(
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
        self, client: TestClient, fake_session: FakeJobSession
    ) -> None:
        fake_session.existing_rows = []
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
