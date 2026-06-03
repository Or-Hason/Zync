"""Shared pytest fixtures: file fixtures, fake DB session, and a wired client.

External boundaries are mocked: the database session is an in-memory fake, the
Ollama client is a stub, and filesystem writes are patched out. Nothing here
touches a real DB, network, or disk.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.resume import Resume
from app.services.ollama_client import get_ollama_client
from tests.helpers import make_docx, make_fake_exe, make_pdf

# A representative raw Ollama JSON object (intentionally messy: extra key, a
# numeric phone, and a stray non-dict experience item to exercise sanitisation).
SAMPLE_OLLAMA_RAW: dict[str, Any] = {
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "phone": 15551234567,
    "summary": "Engineer.",
    "skills": ["Python", "", "FastAPI", 7],
    "experience": [
        {
            "title": "Senior Engineer",
            "company": "Acme",
            "start_date": "2022",
            "end_date": "Present",
            "description": "Lead.",
        },
        "not-an-object",
        {"title": "Engineer", "company": "Globex", "end_date": "2021"},
    ],
    "projects": [{"name": "Zync", "technologies": ["Python", "React"]}],
    "languages": [{"language": "English", "proficiency_level": "Native"}],
    "unexpected_key": "discard me",
}


@pytest.fixture
def pdf_bytes() -> bytes:
    """Return a valid single-page PDF with sample resume text."""
    return make_pdf(["Jane Doe", "Senior Software Engineer", "jane@example.com"])


@pytest.fixture
def docx_bytes() -> bytes:
    """Return a valid DOCX with sample resume text."""
    return make_docx(["John Smith", "Backend Engineer", "john@example.com"])


@pytest.fixture
def exe_bytes() -> bytes:
    """Return bytes resembling a Windows executable (spoofed upload)."""
    return make_fake_exe()


class FakeResult:
    """Minimal stand-in for a SQLAlchemy ``Result`` over preset rows."""

    def __init__(self, rows: list[Resume]) -> None:
        self._rows = rows

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[Resume]:
        return list(self._rows)


class FakeSession:
    """In-memory async session double covering the calls the API makes."""

    def __init__(self) -> None:
        self.added: list[Resume] = []
        self.rows: list[Resume] = []
        self.get_map: dict[UUID, Resume] = {}

    def add(self, obj: Resume) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            _ensure_created_at(obj)

    async def refresh(self, obj: Resume) -> None:
        _ensure_created_at(obj)

    async def get(self, _model: type[Resume], pk: UUID) -> Resume | None:
        return self.get_map.get(pk)

    async def execute(self, _stmt: Any) -> FakeResult:
        return FakeResult(self.rows)

    async def commit(self) -> None:  # pragma: no cover - no-op in fake
        return None

    async def rollback(self) -> None:  # pragma: no cover - no-op in fake
        return None


def _ensure_created_at(obj: Resume) -> None:
    """Populate ``created_at`` the way a real DB server default would."""
    if getattr(obj, "created_at", None) is None:
        obj.created_at = datetime.now(timezone.utc)


class FakeOllamaClient:
    """Stub Ollama client returning a preset payload and recording calls."""

    def __init__(self) -> None:
        self.payload: dict[str, Any] = dict(SAMPLE_OLLAMA_RAW)
        self.calls: list[tuple[str, str]] = []

    async def parse_resume(self, raw_text: str, filename: str) -> dict[str, Any]:
        self.calls.append((raw_text, filename))
        return self.payload


@pytest.fixture
def fake_session() -> FakeSession:
    """Return a fresh in-memory session double."""
    return FakeSession()


@pytest.fixture
def fake_ollama() -> FakeOllamaClient:
    """Return a fresh Ollama client stub."""
    return FakeOllamaClient()


@pytest.fixture
def client(
    fake_session: FakeSession,
    fake_ollama: FakeOllamaClient,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[TestClient]:
    """Yield a TestClient with DB, Ollama, and file storage mocked out."""

    async def fake_save(_data: bytes, kind: str) -> Path:
        return Path(f"/uploads/fake.{kind}")

    monkeypatch.setattr("app.api.resumes.save_upload", fake_save)

    async def _override_get_db() -> AsyncIterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_ollama_client] = lambda: fake_ollama

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
