"""Tests for title-weighted TF-IDF duplicate detection with time-decay rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.duplicate_detection import (
    ExistingJob,
    _comparison_string,
    detect_duplicate,
)

_NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)
_RECENT = _NOW - timedelta(days=30)
_OLD = _NOW - timedelta(days=200)

_TITLE = "Senior Backend Engineer"
_DESCRIPTION = "Build and scale async FastAPI services backed by PostgreSQL."


def _existing(title: str, description: str, created_at: datetime) -> ExistingJob:
    return ExistingJob(
        job_title=title, job_description=description, created_at=created_at
    )


class TestComparisonString:
    """The comparison string concatenates title and description."""

    def test_concatenates_title_and_description(self) -> None:
        assert _comparison_string("Engineer", "Writes code") == "Engineer Writes code"

    def test_handles_missing_parts(self) -> None:
        assert _comparison_string(None, "Only desc") == "Only desc"
        assert _comparison_string("Only title", None) == "Only title"


class TestTimeDecayRules:
    """Recency governs whether a strong match is a duplicate."""

    def test_recent_strong_match_is_duplicate(self) -> None:
        existing = [_existing(_TITLE, _DESCRIPTION, _RECENT)]
        result = detect_duplicate(_TITLE, _DESCRIPTION, existing, now=_NOW)
        assert result.is_duplicate is True
        assert result.duplicate_chance >= 85

    def test_old_strong_match_is_reapplication_candidate(self) -> None:
        existing = [_existing(_TITLE, _DESCRIPTION, _OLD)]
        result = detect_duplicate(_TITLE, _DESCRIPTION, existing, now=_NOW)
        # Old but similar: not an outright duplicate, but flagged proportionally.
        assert result.is_duplicate is False
        assert result.duplicate_chance > 0

    def test_unique_job_is_not_duplicate(self) -> None:
        existing = [
            _existing(
                "Pastry Chef",
                "Bake croissants and manage the morning kitchen rota.",
                _RECENT,
            )
        ]
        result = detect_duplicate(_TITLE, _DESCRIPTION, existing, now=_NOW)
        assert result.is_duplicate is False
        assert result.duplicate_chance == 0

    def test_no_existing_jobs_is_unique(self) -> None:
        result = detect_duplicate(_TITLE, _DESCRIPTION, [], now=_NOW)
        assert result.is_duplicate is False
        assert result.duplicate_chance == 0


class TestTitleParticipatesInSimilarity:
    """Similarity uses title + description, not the description alone."""

    def test_differing_title_lowers_similarity(self) -> None:
        existing = [_existing(_TITLE, _DESCRIPTION, _RECENT)]

        identical = detect_duplicate(_TITLE, _DESCRIPTION, existing, now=_NOW)
        # Same description, a wildly different title: if similarity were computed
        # on the description alone this would also score 100.
        differing_title = detect_duplicate(
            "Retail Fashion Store Manager", _DESCRIPTION, existing, now=_NOW
        )

        assert identical.duplicate_chance == 100
        assert differing_title.duplicate_chance < identical.duplicate_chance
