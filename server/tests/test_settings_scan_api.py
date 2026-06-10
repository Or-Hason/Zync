"""Endpoint tests for the auto-scan settings API (GET/PUT /api/settings/scan)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.resume import Resume
from app.services.settings_store import get_settings_store

_DEFAULT_SCAN = {
    "auto_scan_enabled": False,
    "scan_frequency_hours": 3,
    "notification_score_threshold": 80,
}


class FakeScanStore:
    """In-memory stand-in exposing the scan-settings store interface."""

    def __init__(self) -> None:
        self.scan = dict(_DEFAULT_SCAN)

    async def get_scan_settings(self) -> dict:
        return dict(self.scan)

    async def update_scan_settings(
        self,
        *,
        auto_scan_enabled: bool,
        scan_frequency_hours: int,
        notification_score_threshold: int,
    ) -> dict:
        self.scan = {
            "auto_scan_enabled": auto_scan_enabled,
            "scan_frequency_hours": scan_frequency_hours,
            "notification_score_threshold": notification_score_threshold,
        }
        return dict(self.scan)


class _ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)


class FakeResumeSession:
    """Minimal session double for load_active_resume only."""

    def __init__(self, active: bool) -> None:
        self._active = active

    async def execute(self, _stmt: Any) -> _ScalarResult:
        if self._active:
            resume = Resume(
                id=uuid4(),
                version_name="CV",
                target_role="Backend",
                structured_data={"target_role": "Backend"},
                raw_text="x",
                file_path="/uploads/cv.pdf",
                is_active=True,
            )
            return _ScalarResult([resume])
        return _ScalarResult([])

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.fixture
def store() -> FakeScanStore:
    return FakeScanStore()


def _client(store: FakeScanStore, *, active_resume: bool) -> Iterator[TestClient]:
    async def _override_db():
        yield FakeResumeSession(active_resume)

    app.dependency_overrides[get_settings_store] = lambda: store
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(store: FakeScanStore) -> Iterator[TestClient]:
    yield from _client(store, active_resume=True)


@pytest.fixture
def client_no_resume(store: FakeScanStore) -> Iterator[TestClient]:
    yield from _client(store, active_resume=False)


class TestGetScanSettings:
    """GET /api/settings/scan."""

    def test_returns_defaults(self, client: TestClient) -> None:
        response = client.get("/api/settings/scan")
        assert response.status_code == 200
        assert response.json() == _DEFAULT_SCAN


class TestPutScanSettings:
    """PUT /api/settings/scan."""

    def test_persists_all_fields(
        self, client: TestClient, store: FakeScanStore
    ) -> None:
        payload = {
            "auto_scan_enabled": True,
            "scan_frequency_hours": 6,
            "notification_score_threshold": 90,
        }
        response = client.put("/api/settings/scan", json=payload)
        assert response.status_code == 200
        assert response.json() == payload
        assert store.scan == payload

    def test_invalid_frequency_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/api/settings/scan",
            json={
                "auto_scan_enabled": False,
                "scan_frequency_hours": 99,
                "notification_score_threshold": 80,
            },
        )
        assert response.status_code == 422

    def test_threshold_out_of_range_returns_422(self, client: TestClient) -> None:
        response = client.put(
            "/api/settings/scan",
            json={
                "auto_scan_enabled": False,
                "scan_frequency_hours": 3,
                "notification_score_threshold": 150,
            },
        )
        assert response.status_code == 422

    def test_enable_without_active_resume_returns_400(
        self, client_no_resume: TestClient, store: FakeScanStore
    ) -> None:
        response = client_no_resume.put(
            "/api/settings/scan",
            json={
                "auto_scan_enabled": True,
                "scan_frequency_hours": 3,
                "notification_score_threshold": 80,
            },
        )
        assert response.status_code == 400
        # The setting must remain disabled when the guard rejects the request.
        assert store.scan["auto_scan_enabled"] is False

    def test_disable_without_active_resume_is_allowed(
        self, client_no_resume: TestClient
    ) -> None:
        response = client_no_resume.put(
            "/api/settings/scan",
            json={
                "auto_scan_enabled": False,
                "scan_frequency_hours": 12,
                "notification_score_threshold": 70,
            },
        )
        assert response.status_code == 200
