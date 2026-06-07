"""Tests for the rule-based system_advice generator."""

from __future__ import annotations

from app.services.system_advice import (
    ADVICE_LOW_SCORE,
    ADVICE_MODERATE,
    ADVICE_OLD_SIMILAR_APPLIED,
    ADVICE_OLD_SIMILAR_NOT_APPLIED,
    ADVICE_OLD_SIMILAR_REJECTED,
    ADVICE_RECENT_DUP_APPLIED,
    ADVICE_RECENT_DUP_NOT_APPLIED,
    ADVICE_RECENT_DUP_REJECTED,
    ADVICE_STRONG,
    ADVICE_UNSCORED,
    build_system_advice,
)


class TestSystemAdviceRules:
    """Each rule fires under its condition, respecting priority order."""

    def test_rule1_low_score(self) -> None:
        advice = build_system_advice(
            match_score=20, is_duplicate=False, duplicate_chance=0
        )
        assert advice == ADVICE_LOW_SCORE

    def test_rule1_low_score_takes_priority_over_duplicate(self) -> None:
        advice = build_system_advice(
            match_score=10, is_duplicate=True, duplicate_chance=95
        )
        assert advice == ADVICE_LOW_SCORE

    def test_rule4_strong_match(self) -> None:
        advice = build_system_advice(
            match_score=85, is_duplicate=False, duplicate_chance=0
        )
        assert advice == ADVICE_STRONG

    def test_rule5_moderate_match(self) -> None:
        advice = build_system_advice(
            match_score=55, is_duplicate=False, duplicate_chance=0
        )
        assert advice == ADVICE_MODERATE

    def test_boundary_70_is_strong(self) -> None:
        assert build_system_advice(
            match_score=70, is_duplicate=False, duplicate_chance=0
        ) == ADVICE_STRONG

    def test_boundary_40_is_moderate(self) -> None:
        assert build_system_advice(
            match_score=40, is_duplicate=False, duplicate_chance=0
        ) == ADVICE_MODERATE


class TestRecentDuplicateAdvice:
    """Recent duplicate phrasing varies by matched job status."""

    def test_not_applied_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=True, duplicate_chance=90,
            matched_job_status="not_applied",
        )
        assert advice == ADVICE_RECENT_DUP_NOT_APPLIED

    def test_auto_rejected_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=True, duplicate_chance=90,
            matched_job_status="auto_rejected",
        )
        assert advice == ADVICE_RECENT_DUP_REJECTED

    def test_applied_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=True, duplicate_chance=90,
            matched_job_status="applied",
        )
        assert advice == ADVICE_RECENT_DUP_APPLIED

    def test_deep_pipeline_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=True, duplicate_chance=90,
            matched_job_status="professional_interview",
        )
        assert advice == ADVICE_RECENT_DUP_APPLIED


class TestOldSimilarAdvice:
    """Old similar job phrasing varies by matched job status."""

    def test_not_applied_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=False, duplicate_chance=60,
            matched_job_status="not_applied",
        )
        assert advice == ADVICE_OLD_SIMILAR_NOT_APPLIED

    def test_auto_rejected_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=False, duplicate_chance=60,
            matched_job_status="auto_rejected",
        )
        assert advice == ADVICE_OLD_SIMILAR_REJECTED

    def test_applied_status(self) -> None:
        advice = build_system_advice(
            match_score=80, is_duplicate=False, duplicate_chance=60,
            matched_job_status="applied",
        )
        assert advice == ADVICE_OLD_SIMILAR_APPLIED


class TestUnscoredFallback:
    """A missing score with no duplicate signal yields the fallback advice."""

    def test_unscored_returns_fallback(self) -> None:
        advice = build_system_advice(
            match_score=None, is_duplicate=False, duplicate_chance=0
        )
        assert advice == ADVICE_UNSCORED

    def test_unscored_but_duplicate_still_advises_duplicate(self) -> None:
        advice = build_system_advice(
            match_score=None, is_duplicate=True, duplicate_chance=90,
            matched_job_status="not_applied",
        )
        assert advice == ADVICE_RECENT_DUP_NOT_APPLIED
