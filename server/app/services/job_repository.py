"""Persistence helpers for the job scrape/score pipeline.

Keeps the ORM construction and the read projections (duplicate scan, score
cache) out of the endpoint so it stays focused on HTTP orchestration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import Integer, cast, func, or_, select, text
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
    source_type: str = "manual",
    search_filters: dict | None = None,
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


async def load_known_source_urls(db: AsyncSession) -> set[str]:
    """Return every non-null ``source_url`` currently stored in ``jobs``.

    Used by the scraper to skip URLs already discovered, so a job is never
    re-fetched or re-scored across scans.

    Args:
        db: Active async DB session.

    Returns:
        A set of known source URLs.
    """
    rows = (await db.execute(select(Job.source_url).where(Job.source_url.isnot(None)))).all()
    return {row.source_url for row in rows}


async def count_jobs_for_source(db: AsyncSession, source: str) -> int:
    """Count jobs whose ``search_filters->>'source'`` equals ``source``.

    Drives "first run" detection per scraper source, so an initial-import cap
    only triggers when *this* scraper has never saved a job — not merely when
    the table is globally empty (manual jobs must not suppress it).

    Args:
        db: Active async DB session.
        source: The scraper source id (e.g. ``"jobmaster"``).

    Returns:
        The number of jobs previously saved by this source.
    """
    stmt = select(func.count()).select_from(Job).where(
        Job.search_filters["source"].astext == source
    )
    return int((await db.execute(stmt)).scalar_one())


async def list_jobs(
    db: AsyncSession,
    *,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_score: int | None = None,
    role: str | None = None,
    company: str | None = None,
    cv_id: UUID | None = None,
    source_type: str | None = None,
    is_new: bool = False,
    is_unread: bool = False,
    skills: list[str] | None = None,
    min_experience: int | None = None,
    status: str | None = None,
) -> list[Job]:
    """Return jobs matching the given filters, newest-first, capped at 200 rows.

    Args:
        db: Active async DB session.
        q: Free-text search across job_title, company_name, job_description.
        date_from: ISO date string (``YYYY-MM-DD``) — only jobs on/after this date.
        date_to: ISO date string (``YYYY-MM-DD``) — only jobs on/before this date.
        min_score: Only include jobs with match_score >= this value.
        role: LIKE filter on job_title.
        company: LIKE filter on company_name.
        cv_id: Exact match on scored_by_resume_id.
        source_type: ``"manual"`` or ``"auto"`` (any non-manual source_type).
        is_new: When True, only jobs created in the last 24 hours.
        is_unread: When True, only jobs where viewed_at IS NULL (user has not viewed the detail).
        skills: Each skill must appear in requirements->skills OR ->recommended_skills.
        min_experience: Lower bound on requirements->years_of_experience.
        status: Exact job status match.

    Returns:
        Filtered list of :class:`Job` rows, ordered by ``created_at`` DESC.
    """
    stmt = select(Job).order_by(Job.created_at.desc()).limit(200)

    if q:
        term = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Job.job_title).like(term),
                func.lower(Job.company_name).like(term),
                func.lower(Job.job_description).like(term),
            )
        )

    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            stmt = stmt.where(Job.created_at >= from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = (datetime.fromisoformat(date_to) + timedelta(days=1)).replace(tzinfo=timezone.utc)
            stmt = stmt.where(Job.created_at < to_dt)
        except ValueError:
            pass

    if min_score is not None:
        stmt = stmt.where(Job.match_score >= min_score)

    if role:
        stmt = stmt.where(func.lower(Job.job_title).like(f"%{role.lower()}%"))

    if company:
        stmt = stmt.where(func.lower(Job.company_name).like(f"%{company.lower()}%"))

    if cv_id is not None:
        stmt = stmt.where(Job.scored_by_resume_id == cv_id)

    if source_type == "auto":
        stmt = stmt.where(Job.source_type != "manual")
    elif source_type == "manual":
        stmt = stmt.where(Job.source_type == "manual")

    if is_new:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = stmt.where(Job.created_at >= cutoff)

    if is_unread:
        stmt = stmt.where(Job.viewed_at.is_(None))

    if skills:
        for skill in skills:
            # Use EXISTS + jsonb_array_elements_text for reliable case-insensitive matching.
            # COALESCE to '[]' handles NULL requirements / missing keys gracefully.
            stmt = stmt.where(
                text(
                    "EXISTS ("
                    "  SELECT 1"
                    "  FROM jsonb_array_elements_text(COALESCE(jobs.requirements->'skills', '[]')) AS s"
                    "  WHERE lower(s) = lower(:skill)"
                    "  UNION ALL"
                    "  SELECT 1"
                    "  FROM jsonb_array_elements_text(COALESCE(jobs.requirements->'recommended_skills', '[]')) AS s2"
                    "  WHERE lower(s2) = lower(:skill)"
                    ")"
                ).bindparams(skill=skill)
            )

    if min_experience is not None:
        stmt = stmt.where(
            cast(Job.requirements["years_of_experience"].astext, Integer) >= min_experience
        )

    if status:
        stmt = stmt.where(Job.status == status)

    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def mark_job_read(db: AsyncSession, job_id: UUID) -> None:
    """Set viewed_at to now() on a job if it has not been viewed yet.

    This is the authoritative write for the Explorer's Unread filter.
    Intentionally leaves notified_at untouched — that column belongs
    exclusively to the notification deduplication system.
    Idempotent — no-op if the job was already marked as read.

    Args:
        db: Active async DB session.
        job_id: The job to mark as read.
    """
    job = await db.get(Job, job_id)
    if job is not None and job.viewed_at is None:
        job.viewed_at = datetime.now(timezone.utc)
        await db.flush()


async def list_job_skills(db: AsyncSession) -> list[str]:
    """Return all distinct skill strings across all jobs' JSONB requirements.

    Unions the ``skills`` and ``recommended_skills`` arrays from every row so
    the Explorer's skill autocomplete reflects the full catalogue.

    Args:
        db: Active async DB session.

    Returns:
        Alphabetically sorted, deduplicated skill strings.
    """
    stmt = text("""
        SELECT DISTINCT skill
        FROM (
            SELECT jsonb_array_elements_text(requirements->'skills') AS skill
            FROM jobs
            WHERE requirements IS NOT NULL
            UNION
            SELECT jsonb_array_elements_text(requirements->'recommended_skills') AS skill
            FROM jobs
            WHERE requirements IS NOT NULL
        ) t
        WHERE skill IS NOT NULL AND skill <> ''
        ORDER BY skill
    """)
    rows = (await db.execute(stmt)).all()
    return [row[0] for row in rows]


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
