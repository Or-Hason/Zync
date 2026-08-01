"""The Explorer grid's filtered job query.

Split out of ``job_repository.py`` — see ``app/services/job_repository.py`` for the re-exported public API.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Integer, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import Job
from app.models.job_score import JobScore


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
    has_cover_letter: bool = False,
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
        min_score: Only include jobs scored >= this value by at least one CV.
        role: LIKE filter on job_title.
        company: LIKE filter on company_name.
        cv_id: Only jobs scored by this resume.
        source_type: ``"manual"`` or ``"auto"`` (any non-manual source_type).
        is_new: When True, only jobs created in the last 24 hours.
        is_unread: When True, only jobs where viewed_at IS NULL (user has not viewed the detail).
        has_cover_letter: When True, only jobs with at least one generated cover letter.
        skills: Each skill must appear in requirements->skills OR ->recommended_skills.
        min_experience: Lower bound on requirements->years_of_experience.
        status: Exact job status match.

    Returns:
        Filtered list of :class:`Job` rows (with ``scores`` and each score's
        ``resume`` eager-loaded), ordered by ``created_at`` DESC.
    """
    stmt = (
        select(Job)
        .options(selectinload(Job.scores).selectinload(JobScore.resume))
        .order_by(Job.created_at.desc())
        .limit(200)
    )

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
        # EXISTS rather than a JOIN so a job with several scores is not duplicated.
        stmt = stmt.where(
            select(func.count())
            .select_from(JobScore)
            .where(JobScore.job_id == Job.id, JobScore.match_score >= min_score)
            .correlate(Job)
            .scalar_subquery()
            > 0
        )

    if role:
        stmt = stmt.where(func.lower(Job.job_title).like(f"%{role.lower()}%"))

    if company:
        stmt = stmt.where(func.lower(Job.company_name).like(f"%{company.lower()}%"))

    if cv_id is not None:
        stmt = stmt.where(
            select(func.count())
            .select_from(JobScore)
            .where(JobScore.job_id == Job.id, JobScore.resume_id == cv_id)
            .correlate(Job)
            .scalar_subquery()
            > 0
        )

    if source_type == "auto":
        stmt = stmt.where(Job.source_type != "manual")
    elif source_type == "manual":
        stmt = stmt.where(Job.source_type == "manual")

    if is_new:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = stmt.where(Job.created_at >= cutoff)

    if is_unread:
        stmt = stmt.where(Job.viewed_at.is_(None))

    if has_cover_letter:
        from app.models.cover_letter import CoverLetter
        stmt = stmt.where(
            select(func.count()).select_from(CoverLetter).where(
                CoverLetter.job_id == Job.id
            ).correlate(Job).scalar_subquery() > 0
        )

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
