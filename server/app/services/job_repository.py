"""Persistence helpers for the job scrape/score pipeline.

Keeps the ORM construction and the read projections (duplicate scan, score
cache) out of the endpoint so it stays focused on HTTP orchestration.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import ParsedJob
from app.services.duplicate_detection import DuplicateAssessment, ExistingJob
from app.services.score_cache import ScoredJob
from app.services.text_similarity import comparison_string

# Cap on existing rows pulled into memory for duplicate comparison.
DUPLICATE_SCAN_LIMIT = 500


def new_job(
    parsed: ParsedJob,
    *,
    raw_content: str | None,
    source_url: str | None,
    assessment: DuplicateAssessment,
    status: str,
    match_score: int | None = None,
    score_details: dict | None = None,
    scored_by_resume_id: UUID | None = None,
) -> Job:
    """Build a ``jobs`` ORM row from parsed data and pipeline results.

    Args:
        parsed: Sanitised extracted job fields.
        raw_content: Normalised raw ingested text (for duplicate detection).
        source_url: Originating URL (``None`` for raw-text ingestion).
        assessment: Duplicate-detection outcome.
        status: The job status to persist.
        match_score: Optional 0–100 score.
        score_details: Optional ``{rationale, matched_skills, missing_skills}``.
        scored_by_resume_id: Resume active at scoring time (if scored).

    Returns:
        A transient :class:`Job` instance (not yet added to a session).
    """
    return Job(
        id=uuid4(),
        company_name=parsed.company_name,
        job_title=parsed.job_title,
        company_description=parsed.company_description,
        job_description=parsed.job_description,
        raw_content=raw_content,
        requirements=parsed.requirements.model_dump(),
        source_type="manual",
        source_url=source_url,
        match_score=match_score,
        scored_by_resume_id=scored_by_resume_id,
        score_details=score_details,
        status=status,
        is_duplicate=assessment.is_duplicate,
        duplicate_chance=assessment.duplicate_chance,
        published_at=parsed.published_at,
        application_options=parsed.application_options or [],
        recommended_apply_method=parsed.recommended_apply_method,
    )


async def load_existing_jobs(db: AsyncSession) -> list[ExistingJob]:
    """Load a capped, lightweight projection of jobs for duplicate detection.

    Args:
        db: Active async DB session.

    Returns:
        Up to :data:`DUPLICATE_SCAN_LIMIT` newest jobs as :class:`ExistingJob`.
    """
    stmt = (
        select(Job.raw_content, Job.created_at, Job.status)
        .order_by(Job.created_at.desc())
        .limit(DUPLICATE_SCAN_LIMIT)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ExistingJob(
            raw_content=row.raw_content,
            created_at=row.created_at,
            status=row.status,
        )
        for row in rows
    ]


async def load_scored_jobs(db: AsyncSession, resume_id: UUID) -> list[ScoredJob]:
    """Load jobs already scored with the given resume, for cache reuse.

    Args:
        db: Active async DB session.
        resume_id: The active resume's id.

    Returns:
        Scored jobs (``match_score`` present) as :class:`ScoredJob` projections.
    """
    stmt = select(
        Job.id,
        Job.job_title,
        Job.job_description,
        Job.match_score,
        Job.score_details,
        Job.raw_content,
    ).where(
        Job.scored_by_resume_id == resume_id,
        Job.match_score.isnot(None),
    )
    rows = (await db.execute(stmt)).all()
    return [
        ScoredJob(
            comparison_text=comparison_string(row.job_title, row.job_description),
            match_score=row.match_score,
            score_details=row.score_details,
            job_id=row.id,
            raw_content=row.raw_content,
        )
        for row in rows
    ]


async def update_job_with_score(
    db: AsyncSession,
    job_id: UUID,
    *,
    match_score: int | None,
    score_details: dict | None,
    scored_by_resume_id: UUID | None,
    status: str,
) -> Job | None:
    """Apply scoring results to an existing job row (e.g. a bypassed blacklist hit).

    Args:
        db: Active async DB session.
        job_id: Primary key of the job to update.
        match_score: New 0–100 score (or ``None``).
        score_details: ``{rationale, matched_skills, missing_skills}`` dict.
        scored_by_resume_id: Resume that produced the score.
        status: New job status after scoring.

    Returns:
        The refreshed :class:`Job` row, or ``None`` when not found.
    """
    job = await db.get(Job, job_id)
    if job is None:
        return None
    job.match_score = match_score
    job.score_details = score_details
    job.scored_by_resume_id = scored_by_resume_id
    job.status = status
    await db.flush()
    await db.refresh(job)
    return job
