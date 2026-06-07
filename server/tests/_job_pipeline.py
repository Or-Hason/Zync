"""Shared fakes and helpers for the job scrape/score pipeline tests.

Not collected by pytest (no ``test_`` prefix). The fake session routes the
three distinct pipeline queries (existing-jobs scan, active-resume lookup,
scored-jobs cache) by inspecting the statement's selected columns.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.job import ScoreResult
from app.services.gemini_client import get_gemini_client
from app.services.ollama_client import get_ollama_client
from app.services.settings_store import get_settings_store

# Kept >= _MIN_DESCRIPTION_LENGTH (100) chars so the sufficiency guard in the
# scrape endpoint admits the stubbed job; the leading sentence is reused by the
# privacy test to assert it is never logged.
SAMPLE_JOB_DESCRIPTION = (
    "Own the async FastAPI platform and PostgreSQL layer. You will design JSONB "
    "schemas, build scraping pipelines, and mentor engineers across the team."
)

# Verbatim core posting content used by duplicate detection (mirrors what
# core_job_posting would contain after AI extraction).
SAMPLE_CORE_JOB_POSTING = (
    "Senior Python Engineer\n\n"
    "Own the async FastAPI platform and PostgreSQL layer. Design JSONB schemas, "
    "build scraping pipelines, and mentor engineers across the team.\n\n"
    "Requirements: Python, FastAPI, 5+ years experience."
)

SAMPLE_JOB_RAW: dict[str, Any] = {
    "company_name": "Acme Corp",
    "job_title": "Senior Python Engineer",
    "company_description": "We ship logistics software.",
    "job_description": SAMPLE_JOB_DESCRIPTION,
    "core_job_posting": SAMPLE_CORE_JOB_POSTING,
    "content_classification": "VALID_JOB",
    "requirements": {
        "inferred_role": None,
        "skills": ["Python", "FastAPI"],
        "recommended_skills": ["Go"],
        "years_of_experience": 5,
        "education": "B.Sc.",
        "other": [],
    },
    "published_at": "2026-05-01",
}


class _Result:
    """Result double exposing both ``.all()`` and ``.scalars().all()``."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalars(self) -> "_Result":
        return self


class ExistingRow:
    """Projection row for the duplicate-scan query (raw-content comparison)."""

    def __init__(
        self, raw_content: str, created_at: datetime, status: str = "not_applied"
    ) -> None:
        self.raw_content = raw_content
        self.created_at = created_at
        self.status = status


class ScoredRow:
    """Projection row for the score-cache query."""

    def __init__(
        self, title: str, description: str, match_score: int, score_details: dict | None
    ) -> None:
        self.job_title = title
        self.job_description = description
        self.match_score = match_score
        self.score_details = score_details


class FakeJobSession:
    """In-memory async session that routes pipeline queries by column set."""

    def __init__(self) -> None:
        self.added: list[Job] = []
        self.existing_rows: list[ExistingRow] = []
        self.scored_rows: list[ScoredRow] = []
        self.active_resumes: list[Resume] = []

    def add(self, obj: Job) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            _ensure_created_at(obj)

    async def refresh(self, obj: Job) -> None:
        _ensure_created_at(obj)

    async def get(self, _model: type, pk: Any) -> Any:
        return next((j for j in self.added if j.id == pk), None)

    async def execute(self, stmt: Any) -> _Result:
        names = [desc.get("name") for desc in stmt.column_descriptions]
        if "match_score" in names:
            return _Result(self.scored_rows)
        if "Resume" in names:
            return _Result(self.active_resumes)
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

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload: dict[str, Any] = dict(payload or SAMPLE_JOB_RAW)
        self.calls: list[str] = []

    async def parse_job(self, raw_text: str) -> dict[str, Any]:
        self.calls.append(raw_text)
        return self.payload


class FakeGemini:
    """Stub Gemini client returning a preset result and recording calls."""

    def __init__(
        self, result: ScoreResult | None = None, configured: bool = True
    ) -> None:
        self.result = result
        self._configured = configured
        self.calls: list[tuple[str | None, dict | None]] = []

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def score(
        self,
        job_title: str | None,
        _job_description: str | None,
        _requirements: dict | None,
        resume_structured: dict | None,
    ) -> ScoreResult | None:
        self.calls.append((job_title, resume_structured))
        return self.result


class FakeBlacklistStore:
    """Stub settings store exposing only the blacklist the pipeline reads."""

    def __init__(self, keywords: list[str] | None = None) -> None:
        self.keywords = keywords or []

    async def get_blacklist(self) -> list[str]:
        return list(self.keywords)


def make_active_resume(structured_data: dict | None = None) -> Resume:
    """Build an active Resume row with optional structured data."""
    return Resume(
        id=uuid4(),
        version_name="Active CV",
        target_role="Backend",
        structured_data=structured_data
        or {"full_name": "Jane Doe", "email": "jane@example.com", "skills": ["Python"]},
        raw_text="raw",
        file_path="/uploads/cv.pdf",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def make_score_result(score: int = 78) -> ScoreResult:
    """Build a representative Gemini score result."""
    return ScoreResult(
        match_score=score,
        rationale="Strong overlap on backend skills.",
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Go"],
    )


@contextmanager
def pipeline_client(
    session: FakeJobSession,
    ollama: FakeJobOllama,
    gemini: FakeGemini,
    store: FakeBlacklistStore,
) -> Iterator[TestClient]:
    """Yield a TestClient with all pipeline dependencies overridden."""

    async def _override_db() -> AsyncIterator[FakeJobSession]:
        yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_ollama_client] = lambda: ollama
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    app.dependency_overrides[get_settings_store] = lambda: store

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
