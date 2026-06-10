"""Tests for TF-IDF score caching (>0.90 reuse via scored_by_resume_id)."""

from __future__ import annotations

from uuid import uuid4

from app.services.score_cache import (
    CACHE_SIMILARITY_THRESHOLD,
    ScoredJob,
    find_cached_score,
)

_DETAILS = {
    "rationale": "Strong overlap on backend skills.",
    "matched_skills": ["Python", "FastAPI"],
    "missing_skills": ["Kubernetes"],
}
_TEXT = "Senior Backend Engineer Build async FastAPI services with PostgreSQL"


class TestFindCachedScore:
    """Cache hit/miss behaviour."""

    def test_identical_job_is_cache_hit(self) -> None:
        scored = [
            ScoredJob(
                comparison_text=_TEXT,
                match_score=82,
                score_details=_DETAILS,
                job_id=uuid4(),
            )
        ]
        result = find_cached_score(_TEXT, scored)
        assert result is not None
        assert result.match_score == 82
        assert result.rationale == "Strong overlap on backend skills."
        assert result.matched_skills == ["Python", "FastAPI"]
        assert result.missing_skills == ["Kubernetes"]

    def test_dissimilar_job_is_cache_miss(self) -> None:
        scored = [
            ScoredJob(
                comparison_text="Pastry Chef Bake croissants and run the kitchen",
                match_score=82,
                score_details=_DETAILS,
                job_id=uuid4(),
            )
        ]
        assert find_cached_score(_TEXT, scored) is None

    def test_empty_scored_jobs_is_miss(self) -> None:
        assert find_cached_score(_TEXT, []) is None

    def test_threshold_is_strictly_above_090(self) -> None:
        # Sanity: the configured threshold matches the spec's ">0.90".
        assert CACHE_SIMILARITY_THRESHOLD == 0.90

    def test_missing_score_details_defaults_to_empty(self) -> None:
        scored = [
            ScoredJob(
                comparison_text=_TEXT,
                match_score=55,
                score_details=None,
                job_id=uuid4(),
            )
        ]
        result = find_cached_score(_TEXT, scored)
        assert result is not None
        assert result.match_score == 55
        assert result.rationale is None
        assert result.matched_skills == []
        assert result.missing_skills == []
