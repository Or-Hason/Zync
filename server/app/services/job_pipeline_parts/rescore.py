"""Re-scoring path for an already-persisted job (skips Ollama entirely).

Split out of ``job_pipeline.py`` — see that module for the re-exported
public API.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.services.gemini_client import GeminiUnavailableError
from app.services.job_pipeline_parts.outcomes import (
    KIND_GEMINI_UNAVAILABLE,
    KIND_GEMINI_UNCONFIGURED,
    KIND_NO_ACTIVE_RESUME,
    KIND_SCORED,
    PipelineOutcome,
    build_score_details,
)
from app.services.job_repository import upsert_job_score
from app.services.system_advice import LOW_SCORE_THRESHOLD, build_system_advice


async def rescore_job(
    *,
    db: AsyncSession,
    gemini,
    job_id: UUID,
) -> PipelineOutcome:
    """Re-score an existing job with the current active resume. Skips Ollama.

    Scores Gemini against the stored job data and UPSERTs the result into the
    ``job_scores`` row for (job, active resume). The job row itself is never
    duplicated — a second CV scoring the same job adds a second ``job_scores``
    row, not a second job.

    Args:
        db: Active async DB session.
        gemini: Gemini client (``is_configured`` + ``score`` coroutine).
        job_id: The job to re-score.

    Returns:
        A :class:`PipelineOutcome`; ``KIND_SCORED`` carries the new score and the
        resume it belongs to.
    """
    from app.api.resumes_active import load_active_resume

    job = await db.get(Job, job_id)
    if job is None:
        return PipelineOutcome(kind=KIND_GEMINI_UNAVAILABLE)

    active_resume = await load_active_resume(db)
    if active_resume is None:
        return PipelineOutcome(kind=KIND_NO_ACTIVE_RESUME, job=job)

    if not gemini.is_configured:
        return PipelineOutcome(kind=KIND_GEMINI_UNCONFIGURED, job=job)

    try:
        score = await gemini.score(
            job.job_title,
            job.job_description,
            job.requirements or {},
            active_resume.structured_data,
        )
    except GeminiUnavailableError:
        return PipelineOutcome(kind=KIND_GEMINI_UNAVAILABLE, job=job)

    if score is not None:
        await upsert_job_score(
            db,
            job_id=job.id,
            resume_id=active_resume.id,
            match_score=score.match_score,
            score_details=build_score_details(score),
        )
        # Only auto-managed statuses follow the score; a user-set status
        # (applied, interviewing, …) is never overwritten by a re-score.
        if job.status in ("not_applied", "auto_rejected"):
            job.status = (
                "auto_rejected"
                if score.match_score < LOW_SCORE_THRESHOLD
                else "not_applied"
            )
        await db.flush()

    await db.refresh(job)

    advice = build_system_advice(
        match_score=score.match_score if score else None,
        is_duplicate=job.is_duplicate,
        duplicate_chance=job.duplicate_chance,
        matched_job_status=None,
    )
    return PipelineOutcome(
        kind=KIND_SCORED,
        job=job,
        score=score,
        advice=advice,
        scored_by_resume_id=active_resume.id if score is not None else None,
    )
