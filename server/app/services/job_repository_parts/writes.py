"""ORM row construction for jobs and job_scores.

Split out of ``job_repository.py`` — see ``app/services/job_repository.py`` for the re-exported public API.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_score import JobScore
from app.schemas.job import ParsedJob
from app.services.duplicate_detection import DuplicateAssessment


def new_job(
    parsed: ParsedJob,
    *,
    raw_content: str | None,
    source_url: str | None,
    assessment: DuplicateAssessment,
    status: str,
    source_type: str = "manual",
    search_filters: dict | None = None,
) -> Job:
    """Build a ``jobs`` ORM row from parsed data and pipeline results.

    Scores are deliberately absent: they belong to :class:`JobScore` rows keyed
    by (job, resume) — see :func:`new_job_score`.

    Args:
        parsed: Sanitised extracted job fields.
        raw_content: Normalised raw ingested text (for duplicate detection).
        source_url: Originating URL (``None`` for raw-text ingestion).
        assessment: Duplicate-detection outcome.
        status: The job status to persist.
        source_type: Ingestion source (``"manual"`` or a scraper id like
            ``"jobmaster"``).
        search_filters: Scraper search metadata persisted to the row's
            ``search_filters`` JSONB column (``None`` for manual ingestion).

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
        source_type=source_type,
        source_url=source_url,
        search_filters=search_filters,
        status=status,
        is_duplicate=assessment.is_duplicate,
        duplicate_chance=assessment.duplicate_chance,
        published_at=parsed.published_at,
        application_options=parsed.application_options or [],
        recommended_apply_method=parsed.recommended_apply_method,
    )


def new_job_score(
    *,
    job_id: UUID,
    resume_id: UUID,
    match_score: int,
    score_details: dict | None,
) -> JobScore:
    """Build a transient ``job_scores`` row for a freshly scored job.

    Only valid for a job that cannot already have a score for this resume (i.e.
    a row created in the same request). Use :func:`upsert_job_score` otherwise.

    Args:
        job_id: The scored job's primary key.
        resume_id: The resume the score was computed against.
        match_score: The 0–100 score.
        score_details: ``{rationale, matched_skills, missing_skills}`` dict.

    Returns:
        A transient :class:`JobScore` instance (not yet added to a session).
    """
    return JobScore(
        id=uuid4(),
        job_id=job_id,
        resume_id=resume_id,
        match_score=match_score,
        score_details=score_details,
    )


async def upsert_job_score(
    db: AsyncSession,
    *,
    job_id: UUID,
    resume_id: UUID,
    match_score: int,
    score_details: dict | None,
) -> JobScore:
    """Insert or update the single score row for a (job, resume) pair.

    Mirrors the ``uq_job_scores_job_resume`` constraint at the application level
    so a re-score overwrites the CV's previous result instead of accumulating
    history rows.

    Args:
        db: Active async DB session.
        job_id: The scored job's primary key.
        resume_id: The resume the score was computed against.
        match_score: The new 0–100 score.
        score_details: ``{rationale, matched_skills, missing_skills}`` dict.

    Returns:
        The persisted :class:`JobScore` row.
    """
    stmt = select(JobScore).where(
        JobScore.job_id == job_id, JobScore.resume_id == resume_id
    )
    existing = (await db.execute(stmt)).scalars().first()

    if existing is not None:
        existing.match_score = match_score
        existing.score_details = score_details
        await db.flush()
        return existing

    score = new_job_score(
        job_id=job_id,
        resume_id=resume_id,
        match_score=match_score,
        score_details=score_details,
    )
    db.add(score)
    await db.flush()
    return score
