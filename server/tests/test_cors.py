"""CORS policy tests.

The packaged desktop app talks to this API cross-origin: its WebView serves the
frontend from a `tauri` scheme while the backend answers on 127.0.0.1:8000. If
those origins fall out of the allow-list the app fails *silently* — every
request is rejected by the browser before it reaches a route, so the backend
logs stay clean and nothing points at the cause. These tests pin the contract.

Preflight (`OPTIONS`) is answered by the middleware itself and never reaches a
route, so nothing here needs a database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Origins the WebView reports, per platform. Windows/WebView2 uses the
# http form; macOS/Linux (WKWebView, WebKitGTK) use the custom scheme.
TAURI_ORIGINS = ["http://tauri.localhost", "tauri://localhost"]

# Dev servers: the Tauri dev window and a plain browser tab.
DEV_ORIGINS = ["http://localhost:1420", "http://localhost:5173"]

# Any real endpoint works — preflight is intercepted before routing.
PREFLIGHT_PATH = "/api/jobs"


@pytest.fixture
def bare_client() -> TestClient:
    """Client with no dependency overrides — preflight never hits the DB."""
    return TestClient(app)


@pytest.mark.parametrize("origin", TAURI_ORIGINS + DEV_ORIGINS)
def test_preflight_allows_known_origin(bare_client: TestClient, origin: str) -> None:
    """Every supported origin gets an echoed allow-origin header."""
    res = bare_client.options(
        PREFLIGHT_PATH,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", TAURI_ORIGINS)
def test_preflight_allows_mutating_methods_from_tauri(
    bare_client: TestClient, origin: str
) -> None:
    """PATCH/POST/DELETE are usable from the packaged app, not just GET."""
    for method in ("POST", "PATCH", "DELETE"):
        res = bare_client.options(
            PREFLIGHT_PATH,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert res.status_code == 200, method
        assert res.headers["access-control-allow-origin"] == origin


def test_preflight_rejects_unknown_origin(bare_client: TestClient) -> None:
    """A remote page must not be able to read this API.

    The endpoints are unauthenticated and serve resume PII, so an origin that
    is not explicitly listed gets no allow-origin header back and the browser
    discards the response.
    """
    res = bare_client.options(
        PREFLIGHT_PATH,
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in res.headers
