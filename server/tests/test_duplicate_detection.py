"""Tests for raw-content TF-IDF duplicate detection with time-decay rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.duplicate_detection import (
    ExistingJob,
    detect_duplicate,
    normalize_content,
)

_NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)
_RECENT = _NOW - timedelta(days=30)
_OLD = _NOW - timedelta(days=200)

_CONTENT = (
    "Senior Backend Engineer. We are hiring an engineer to build and scale "
    "asynchronous FastAPI services backed by PostgreSQL. You will own the data "
    "pipeline, design JSONB schemas, and mentor junior developers."
)


def _existing(raw_content: str, created_at: datetime) -> ExistingJob:
    return ExistingJob(raw_content=raw_content, created_at=created_at)


class TestNormalizeContent:
    """Normalisation collapses whitespace and lowercases for stable matching."""

    def test_collapses_whitespace_and_lowercases(self) -> None:
        assert normalize_content("  Hello\n\nWORLD  ") == "hello world"

    def test_handles_none_and_blank(self) -> None:
        assert normalize_content(None) == ""
        assert normalize_content("   ") == ""


class TestTimeDecayRules:
    """Recency governs whether a strong match is a duplicate."""

    def test_recent_identical_content_is_duplicate(self) -> None:
        existing = [_existing(_CONTENT, _RECENT)]
        result = detect_duplicate(_CONTENT, existing, now=_NOW)
        assert result.is_duplicate is True
        assert result.duplicate_chance >= 85

    def test_minor_edits_still_detected(self) -> None:
        # Two incidental lines removed: raw-content similarity must stay high
        # enough to still flag the near-identical posting.
        edited = _CONTENT.replace("Senior Backend Engineer. ", "").replace(
            " and mentor junior developers.", "."
        )
        existing = [_existing(_CONTENT, _RECENT)]
        result = detect_duplicate(edited, existing, now=_NOW)
        assert result.is_duplicate is True

    def test_old_strong_match_is_reapplication_candidate(self) -> None:
        existing = [_existing(_CONTENT, _OLD)]
        result = detect_duplicate(_CONTENT, existing, now=_NOW)
        assert result.is_duplicate is False
        assert result.duplicate_chance > 0

    def test_unique_job_is_not_duplicate(self) -> None:
        existing = [
            _existing(
                "Pastry Chef. Bake croissants and manage the morning kitchen rota.",
                _RECENT,
            )
        ]
        result = detect_duplicate(_CONTENT, existing, now=_NOW)
        assert result.is_duplicate is False
        assert result.duplicate_chance == 0

    def test_no_existing_jobs_is_unique(self) -> None:
        result = detect_duplicate(_CONTENT, [], now=_NOW)
        assert result.is_duplicate is False
        assert result.duplicate_chance == 0

    def test_blank_candidate_is_unique(self) -> None:
        existing = [_existing(_CONTENT, _RECENT)]
        result = detect_duplicate(None, existing, now=_NOW)
        assert result.is_duplicate is False
        assert result.duplicate_chance == 0
