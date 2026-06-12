"""Tests for Gemini PII stripping, prompt building, response parsing, and model fallback."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import app.services.gemini_client as _gc_module
from app.services.gemini_client import GeminiClient, GeminiUnavailableError
from app.services.gemini_scoring import (
    PII_FIELDS,
    build_scoring_prompt,
    parse_score_response,
    strip_pii,
)

from google.genai.errors import ClientError

def _rate_limit_error() -> ClientError:
    """Return a ClientError representing a hard quota exhaustion (RESOURCE_EXHAUSTED)."""
    return ClientError(429, {"error": {"code": 429, "message": "rate limited", "status": "RESOURCE_EXHAUSTED"}})


def _burst_error() -> ClientError:
    """Return a ClientError representing a soft burst/RPM limit (no quota keywords)."""
    return ClientError(429, {"error": {"code": 429, "message": "Too Many Requests", "status": "RATE_LIMIT_EXCEEDED"}})


@pytest.fixture()
def _reset_rotation_state():
    """Reset module-level rotation globals before and after each test."""
    _gc_module.current_model_index = 0
    _gc_module.last_rotated_at = None
    yield
    _gc_module.current_model_index = 0
    _gc_module.last_rotated_at = None

_RESUME = {
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+15551234567",
    "location": "Berlin",
    "linkedin_url": "https://linkedin.com/in/jane",
    "github_url": "https://github.com/jane",
    "portfolio_url": "https://jane.dev",
    "summary": "Backend engineer with 6 years of Python.",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}


class TestStripPii:
    """PII fields are removed; everything else is retained."""

    def test_all_pii_fields_removed(self) -> None:
        clean = strip_pii(_RESUME)
        for field in PII_FIELDS:
            assert field not in clean

    def test_non_pii_retained(self) -> None:
        clean = strip_pii(_RESUME)
        assert clean["summary"].startswith("Backend engineer")
        assert clean["skills"] == ["Python", "FastAPI", "PostgreSQL"]

    def test_none_input_returns_empty_dict(self) -> None:
        assert strip_pii(None) == {}


class TestBuildScoringPrompt:
    """The prompt embeds job data and only the anonymised resume."""

    def test_prompt_excludes_pii_values(self) -> None:
        clean = strip_pii(_RESUME)
        prompt = build_scoring_prompt(
            "Backend Engineer", "Build APIs", {"skills": ["Python"]}, clean
        )
        assert "jane@example.com" not in prompt
        assert "+15551234567" not in prompt
        assert "Jane Doe" not in prompt
        # Job and non-PII resume content is present.
        assert "Backend Engineer" in prompt
        assert "FastAPI" in prompt


class TestParseScoreResponse:
    """Robust parsing/validation of Gemini output."""

    def test_valid_response(self) -> None:
        text = (
            '{"match_score": 78, "rationale": "Good fit.", '
            '"matched_skills": ["Python"], "missing_skills": ["Go"]}'
        )
        result = parse_score_response(text)
        assert result is not None
        assert result.match_score == 78
        assert result.rationale == "Good fit."
        assert result.matched_skills == ["Python"]
        assert result.missing_skills == ["Go"]

    def test_fenced_json_is_recovered(self) -> None:
        text = '```json\n{"match_score": 50, "rationale": "ok"}\n```'
        result = parse_score_response(text)
        assert result is not None
        assert result.match_score == 50

    def test_score_is_clamped_to_range(self) -> None:
        assert parse_score_response('{"match_score": 250}').match_score == 100
        assert parse_score_response('{"match_score": -10}').match_score == 0

    def test_malformed_json_returns_none(self) -> None:
        assert parse_score_response("not json at all") is None

    def test_missing_score_returns_none(self) -> None:
        assert parse_score_response('{"rationale": "no score here"}') is None

    def test_non_numeric_score_returns_none(self) -> None:
        assert parse_score_response('{"match_score": "high"}') is None

    def test_non_string_skills_are_dropped(self) -> None:
        result = parse_score_response(
            '{"match_score": 60, "matched_skills": ["Python", 7, ""]}'
        )
        assert result is not None
        assert result.matched_skills == ["Python"]


class TestApiKeyNeverLogged:
    """The API key must never reach log output, even on failure."""

    @pytest.mark.asyncio
    async def test_key_absent_from_failure_logs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = GeminiClient(
            api_key="SECRET_KEY_XYZ",
            models=["gemini-3.5-flash"],
            timeout_seconds=5,
        )

        def _boom(_prompt: str) -> str:
            raise RuntimeError("upstream 503 error")

        # Patch _generate_with_fallback so _boom receives the full prompt arg.
        monkeypatch.setattr(client, "_generate_with_fallback", _boom)

        with caplog.at_level(logging.ERROR):
            result = await client.score("Engineer", "desc", {}, {"skills": ["Python"]})

        assert result is None
        assert "SECRET_KEY_XYZ" not in caplog.text


class TestModelFallback:
    """Stateful model rotation on 429 errors."""

    MODELS = ["model-a", "model-b", "model-c"]

    def _client(self) -> GeminiClient:
        return GeminiClient(api_key="key", models=self.MODELS, timeout_seconds=5)

    def test_rotation_on_rate_limit(
        self, monkeypatch: pytest.MonkeyPatch, _reset_rotation_state: None
    ) -> None:
        """First model raises 429; second succeeds — result is returned."""
        client = self._client()
        calls: list[str] = []

        def _generate(_prompt: str, model: str) -> str:
            calls.append(model)
            if model == "model-a":
                raise _rate_limit_error()
            return '{"match_score": 80, "rationale": "ok"}'

        monkeypatch.setattr(client, "_generate", _generate)
        result = client._generate_with_fallback("prompt")

        assert result == '{"match_score": 80, "rationale": "ok"}'
        assert calls == ["model-a", "model-b"]
        assert _gc_module.current_model_index == 1
        assert _gc_module.last_rotated_at is not None

    def test_all_models_exhausted_raises(
        self, monkeypatch: pytest.MonkeyPatch, _reset_rotation_state: None
    ) -> None:
        """All models rate-limited → GeminiUnavailableError; index left at last rotation."""
        client = self._client()

        monkeypatch.setattr(
            client,
            "_generate",
            MagicMock(side_effect=_rate_limit_error()),
        )

        with pytest.raises(GeminiUnavailableError):
            client._generate_with_fallback("prompt")

        # Index should have rotated through all 3 models (wraps back to 0).
        assert _gc_module.last_rotated_at is not None

    @pytest.mark.asyncio
    async def test_exhaustion_propagates_as_503_from_score(
        self, monkeypatch: pytest.MonkeyPatch, _reset_rotation_state: None
    ) -> None:
        """GeminiUnavailableError is re-raised by score(), not swallowed."""
        client = self._client()

        def _always_unavailable(_prompt: str) -> str:
            raise GeminiUnavailableError("all exhausted")

        monkeypatch.setattr(client, "_generate_with_fallback", _always_unavailable)

        with pytest.raises(GeminiUnavailableError):
            await client.score("Engineer", "desc", {}, {})

    def test_burst_retries_then_rotation(
        self, monkeypatch: pytest.MonkeyPatch, _reset_rotation_state: None
    ) -> None:
        """Burst 429s retry the current model 3×, then rotate to the next."""
        client = self._client()
        calls: list[str] = []
        slept: list[float] = []

        def _generate(_prompt: str, model: str) -> str:
            calls.append(model)
            if model == "model-a":
                raise _burst_error()
            return '{"match_score": 55, "rationale": "ok"}'

        monkeypatch.setattr(client, "_generate", _generate)
        monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

        result = client._generate_with_fallback("prompt")

        assert result == '{"match_score": 55, "rationale": "ok"}'
        # 3 attempts on model-a (all burst 429), then 1 successful on model-b.
        assert calls == ["model-a", "model-a", "model-a", "model-b"]
        # Back-off sleeps: 2 s after attempt 1, 4 s after attempt 2.
        assert slept == [2, 4]
        assert _gc_module.current_model_index == 1
        assert _gc_module.last_rotated_at is not None

    def test_one_hour_reset(
        self, monkeypatch: pytest.MonkeyPatch, _reset_rotation_state: None
    ) -> None:
        """Index resets to 0 when called more than 1 hour after the last rotation."""
        client = self._client()
        _gc_module.current_model_index = 2
        _gc_module.last_rotated_at = datetime.now(timezone.utc) - timedelta(hours=1, seconds=1)

        monkeypatch.setattr(
            client, "_generate", lambda _prompt, model: '{"match_score": 50}'
        )
        client._generate_with_fallback("prompt")

        # The reset fires before the call, so the successful call uses index 0.
        assert _gc_module.last_rotated_at is None
