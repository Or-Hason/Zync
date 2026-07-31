"""Selection and projection helpers for a job's per-CV scores.

A job carries one :class:`~app.models.job_score.JobScore` per resume that has
scored it. Endpoints returning a *single* score (the Job Card, notification
deep-links) need a deterministic rule for which one to surface; endpoints
returning the whole set (the Explorer grid) need it projected with CV names.

The single-score rule mirrors the Explorer's priority logic so the detail view
and the grid never disagree: the active CV wins, otherwise the highest score.
"""

from __future__ import annotations

from uuid import UUID

from app.models.job_score import JobScore
from app.schemas.job import JobScoreItem, ScoreResult


def select_score(scores: list[JobScore], active_resume_id: UUID | None) -> JobScore | None:
    """Pick the score to surface for a job: active CV first, else best match.

    Args:
        scores: All ``job_scores`` rows for one job.
        active_resume_id: The currently active resume, or ``None`` when unset.

    Returns:
        The selected :class:`JobScore`, or ``None`` when the job is unscored.
    """
    if not scores:
        return None
    if active_resume_id is not None:
        for score in scores:
            if score.resume_id == active_resume_id:
                return score
    return max(scores, key=lambda s: s.match_score)


def to_score_result(score: JobScore) -> ScoreResult:
    """Rebuild the Job Card's score payload from a stored score row.

    Args:
        score: The ``job_scores`` row to project.

    Returns:
        The :class:`ScoreResult` the frontend's Job Card renders. Missing
        ``score_details`` keys degrade to ``None`` / empty lists rather than
        raising — the JSONB blob is model output and may be partial.
    """
    details = score.score_details or {}
    return ScoreResult(
        match_score=score.match_score,
        rationale=details.get("rationale"),
        matched_skills=details.get("matched_skills") or [],
        missing_skills=details.get("missing_skills") or [],
    )


def to_score_items(scores: list[JobScore]) -> list[JobScoreItem]:
    """Project ORM score rows into the Explorer payload, resolving each CV name.

    Args:
        scores: Eager-loaded ``job_scores`` rows (each with ``resume`` loaded).

    Returns:
        One :class:`JobScoreItem` per CV, highest score first so the grid's
        "best match" lookup is a head read.
    """
    items = [
        JobScoreItem(
            resume_id=s.resume_id,
            resume_name=s.resume.version_name if s.resume is not None else None,
            match_score=s.match_score,
        )
        for s in scores
    ]
    return sorted(items, key=lambda i: i.match_score, reverse=True)
