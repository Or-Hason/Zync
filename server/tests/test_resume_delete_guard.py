"""Tests for DELETE /api/resumes/{id} and its auto-scan disable guard."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.resume import Resume
from app.services.settings_store import get_settings_store


def _make_resume(*, is_active: bool) -> Resume:
    return Resume(
        id=uuid4(),
        version_name="CV",
        target_role="Backend",
        structured_data={"target_role": "Backend"},
        raw_text="x",
        file_path="/uploads/cv.pdf",
        is_active=is_active,
    )


class FakeDeleteSession:
    """Session double covering get/execute/flush for the delete endpoint.

    The endpoint deletes via a Core ``DELETE`` statement (``db.execute``), so the
    fake records executed deletes rather than ORM ``db.delete`` calls.
    """

    def __init__(self, resume: Resume | None) -> None:
        self._resume = resume
        self.delete_count = 0

    async def get(self, _model: type, pk: UUID) -> Resume | None:
        if self._resume is not None and self._resume.id == pk:
            return self._resume
        return None

    async def execute(self, _stmt: Any) -> None:
        self.delete_count += 1

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeAutoScanStore:
    """Store double recording auto_scan_enabled writes."""

    def __init__(self) -> None:
        self.set_calls: list[bool] = []

    async def set_auto_scan_enabled(self, enabled: bool) -> None:
        self.set_calls.append(enabled)


@pytest.fixture
def store() -> FakeAutoScanStore:
    return FakeAutoScanStore()


def _client(session: FakeDeleteSession, store: FakeAutoScanStore) -> Iterator[TestClient]:
    async def _override_db() -> Any:
        yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestDeleteActiveResume:
    """Deleting the active resume must disable auto-scan."""

    def test_disables_auto_scan(self, store: FakeAutoScanStore) -> None:
        resume = _make_resume(is_active=True)
        session = FakeDeleteSession(resume)
        for client in _client(session, store):
            response = client.delete(f"/api/resumes/{resume.id}")
        assert response.status_code == 204
        assert session.delete_count == 1
        assert store.set_calls == [False]


class TestDeleteNonActiveResume:
    """Deleting a non-active resume must NOT touch auto-scan."""

    def test_leaves_auto_scan_untouched(self, store: FakeAutoScanStore) -> None:
        resume = _make_resume(is_active=False)
        session = FakeDeleteSession(resume)
        for client in _client(session, store):
            response = client.delete(f"/api/resumes/{resume.id}")
        assert response.status_code == 204
        assert session.delete_count == 1
        assert store.set_calls == []


class TestDeleteMissingResume:
    """A missing resume yields 404 and no side effects."""

    def test_returns_404(self, store: FakeAutoScanStore) -> None:
        session = FakeDeleteSession(None)
        for client in _client(session, store):
            response = client.delete(f"/api/resumes/{uuid4()}")
        assert response.status_code == 404
        assert session.delete_count == 0
        assert store.set_calls == []
