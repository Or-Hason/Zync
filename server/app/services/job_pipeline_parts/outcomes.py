"""Shared outcome type, kind constants, and score-projection helper.

Split out of ``job_pipeline.py`` — see that module for the re-exported
public API.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.job import Job
from app.schemas.job import ParsedJob, ScoreResult

# Outcome kinds returned by :func:`run_job_pipeline`.
KIND_CLASSIFICATION_REJECTED = "classification_rejected"
KIND_CACHE_HIT = "cache_hit"
KIND_BLACKLISTED = "blacklisted"
KIND_NO_ACTIVE_RESUME = "no_active_resume"
KIND_GEMINI_UNCONFIGURED = "gemini_unconfigured"
KIND_GEMINI_UNAVAILABLE = "gemini_unavailable"
KIND_OLLAMA_PARSE_FAILURE = "ollama_parse_failure"
KIND_SCORED = "scored"


@dataclass
class PipelineOutcome:
    """Structured result of one pipeline run (transport-agnostic).

    Attributes:
        kind: One of the ``KIND_*`` constants describing what happened.
        parsed: The sanitised parsed job (always set once extraction succeeds).
        job: The persisted (or pre-existing) job row, when one is involved.
        score: The score result on a scored run or cache hit.
        advice: The generated ``system_advice`` string when scored/cached.
        score_cached: Whether the score was reused from cache.
        blacklist_keyword: The matched keyword on a blacklist rejection.
        scored_by_resume_id: The resume :attr:`score` was computed against.
            ``None`` when nothing was scored — the job row itself no longer
            carries this, it lives on the ``job_scores`` row.
    """

    kind: str
    parsed: ParsedJob | None = None
    job: Job | None = None
    score: ScoreResult | None = None
    advice: str | None = None
    score_cached: bool = False
    blacklist_keyword: str | None = None
    scored_by_resume_id: UUID | None = None


def build_score_details(score: ScoreResult) -> dict:
    """Project a :class:`ScoreResult` into the ``score_details`` JSONB shape.

    Args:
        score: The Gemini (or cached) scoring result.

    Returns:
        The ``{rationale, matched_skills, missing_skills}`` dict persisted on the
        ``job_scores`` row and replayed by the score cache.
    """
    return {
        "rationale": score.rationale,
        "matched_skills": score.matched_skills,
        "missing_skills": score.missing_skills,
    }
