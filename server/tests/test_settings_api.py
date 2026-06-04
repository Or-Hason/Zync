"""Endpoint tests for the settings (blacklist + bypass preference) API."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.settings_store import (
    DuplicateKeywordError,
    get_settings_store,
)


class FakeSettingsStore:
    """In-memory stand-in for SettingsStore mirroring its async interface."""

    def __init__(self) -> None:
        self.keywords: list[str] = []
        self.preference: str = "ask"

    async def get_blacklist(self) -> list[str]:
        return list(self.keywords)

    async def add_keyword(self, keyword: str) -> list[str]:
        cleaned = keyword.strip()
        if not cleaned:
            raise ValueError("blank")
        if any(cleaned.lower() == k.lower() for k in self.keywords):
            raise DuplicateKeywordError(cleaned)
        self.keywords.append(cleaned)
        return list(self.keywords)

    async def remove_keyword(self, keyword: str) -> list[str]:
        target = keyword.strip().lower()
        self.keywords = [k for k in self.keywords if k.lower() != target]
        return list(self.keywords)

    async def get_bypass_preference(self) -> str:
        return self.preference

    async def set_bypass_preference(self, preference: str) -> None:
        self.preference = preference


@pytest.fixture
def store() -> FakeSettingsStore:
    return FakeSettingsStore()


@pytest.fixture
def client(store: FakeSettingsStore) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestBlacklistCrud:
    """GET / POST / DELETE /api/settings/blacklist."""

    def test_get_empty_blacklist(self, client: TestClient) -> None:
        response = client.get("/api/settings/blacklist")
        assert response.status_code == 200
        assert response.json() == {"keywords": []}

    def test_add_keyword(self, client: TestClient) -> None:
        response = client.post("/api/settings/blacklist", json={"keyword": "PHP"})
        assert response.status_code == 201
        assert response.json()["keywords"] == ["PHP"]

    def test_add_duplicate_returns_409(
        self, client: TestClient, store: FakeSettingsStore
    ) -> None:
        store.keywords = ["PHP"]
        response = client.post("/api/settings/blacklist", json={"keyword": "php"})
        assert response.status_code == 409

    def test_delete_keyword(
        self, client: TestClient, store: FakeSettingsStore
    ) -> None:
        store.keywords = ["PHP", "Drupal"]
        response = client.delete("/api/settings/blacklist/PHP")
        assert response.status_code == 200
        assert response.json()["keywords"] == ["Drupal"]


class TestBypassPreference:
    """GET / PUT /api/settings/blacklist-bypass-preference."""

    def test_get_default_preference(self, client: TestClient) -> None:
        response = client.get("/api/settings/blacklist-bypass-preference")
        assert response.status_code == 200
        assert response.json() == {"preference": "ask"}

    def test_put_persists_preference(
        self, client: TestClient, store: FakeSettingsStore
    ) -> None:
        response = client.put(
            "/api/settings/blacklist-bypass-preference",
            json={"preference": "always"},
        )
        assert response.status_code == 200
        assert response.json() == {"preference": "always"}
        assert store.preference == "always"

    def test_invalid_preference_rejected_422(self, client: TestClient) -> None:
        response = client.put(
            "/api/settings/blacklist-bypass-preference",
            json={"preference": "sometimes"},
        )
        assert response.status_code == 422
