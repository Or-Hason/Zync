"""Explorer list/query endpoints: ``GET /jobs`` and ``GET /jobs/skills``.

Split out of ``jobs.py`` — see ``app/api/jobs.py`` for how these sub-routers are assembled.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.job import JobListItem
from app.services.job_repository import list_job_skills, list_jobs
from app.services.score_selection import to_score_items

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=list[JobListItem],
    summary="List jobs with optional filtering for the Explorer view",
)
async def list_jobs_endpoint(
    q: str | None = Query(None, description="Free-text search across role, company, description"),
    date_from: str | None = Query(None, description="ISO date (YYYY-MM-DD) for range start, inclusive"),
    date_to: str | None = Query(None, description="ISO date (YYYY-MM-DD) for range end, inclusive"),
    min_score: int | None = Query(None, ge=0, le=100, description="Minimum match score"),
    role: str | None = Query(None, description="LIKE filter on job title"),
    company: str | None = Query(None, description="LIKE filter on company name"),
    cv_id: str | None = Query(None, description="UUID of the CV used for scoring"),
    source_type: str | None = Query(None, description="manual or auto"),
    is_new: bool = Query(False, description="Only jobs created in the last 24 hours"),
    is_unread: bool = Query(False, description="Only jobs where viewed_at IS NULL (user has not viewed the detail)"),
    has_cover_letter: bool = Query(False, description="Only jobs with generated cover letters"),
    skills: list[str] = Query(default_factory=list, description="Required skills (multi)"),
    min_experience: int | None = Query(None, ge=0, description="Minimum years of experience"),
    job_status: str | None = Query(None, alias="status", description="Exact status match"),
    db: AsyncSession = Depends(get_db),
) -> list[JobListItem]:
    """Return up to 200 jobs matching the given filters, newest first.

    Each item carries a ``scores`` array — one entry per CV that has scored the
    job, with the CV's name resolved from the eager-loaded ``resumes`` join. The
    grid decides which entry to surface (active CV first, or best match); the API
    stays presentation-agnostic.

    All filter params are optional; omitting them returns all jobs (capped at 200).
    Returns an empty list (not 404) when no jobs match.
    """
    from uuid import UUID as _UUID

    cv_uuid: _UUID | None = None
    if cv_id:
        try:
            cv_uuid = _UUID(cv_id)
        except ValueError:
            return []

    rows = await list_jobs(
        db,
        q=q,
        date_from=date_from,
        date_to=date_to,
        min_score=min_score,
        role=role,
        company=company,
        cv_id=cv_uuid,
        source_type=source_type,
        is_new=is_new,
        is_unread=is_unread,
        has_cover_letter=has_cover_letter,
        skills=skills or [],
        min_experience=min_experience,
        status=job_status,
    )

    job_ids = [j.id for j in rows]

    # Query which jobs have cover letters.
    from app.models.cover_letter import CoverLetter
    cover_letter_jobs = set(
        (await db.execute(
            select(CoverLetter.job_id).where(CoverLetter.job_id.in_(job_ids)).distinct()
        )).scalars().all()
    )

    items: list[JobListItem] = [
        JobListItem.model_validate(j).model_copy(
            update={
                "scores": to_score_items(j.scores),
                "has_cover_letter": j.id in cover_letter_jobs,
            }
        )
        for j in rows
    ]

    logger.info("Jobs listed", extra={"count": len(items)})
    return items


@router.get(
    "/skills",
    response_model=list[str],
    summary="All distinct skill strings across jobs JSONB requirements (for autocomplete)",
)
async def get_job_skills(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return a deduplicated, alphabetically sorted list of all skills in the DB.

    Unions ``requirements->skills`` and ``requirements->recommended_skills``
    from every job row. Used to populate the Explorer's skills autocomplete.
    """
    return await list_job_skills(db)
