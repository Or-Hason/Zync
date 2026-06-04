"""Tests for Gemini PII stripping, prompt building, and response parsing."""

from __future__ import annotations

import logging

import pytest

from app.services.gemini_client import (
    PII_FIELDS,
    GeminiClient,
    build_scoring_prompt,
    parse_score_response,
    strip_pii,
)

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
            api_key="SECRET_KEY_XYZ", model="gemini-3.5-flash", timeout_seconds=5
        )

        def _boom(_prompt: str) -> str:
            raise RuntimeError("upstream 503 error")

        monkeypatch.setattr(client, "_generate", _boom)

        with caplog.at_level(logging.ERROR):
            result = await client.score("Engineer", "desc", {}, {"skills": ["Python"]})

        assert result is None
        assert "SECRET_KEY_XYZ" not in caplog.text
