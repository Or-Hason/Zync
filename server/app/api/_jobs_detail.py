"""Read/unread mutations and single-job lookups for ``/jobs/{job_id}``.

Split out of ``jobs.py`` — see ``app/api/jobs.py`` for how these sub-routers are assembled.
The read-all route is declared before the ``{job_id}/read`` route so that a literal
``/jobs/read-all`` path is not captured by the ``{job_id}`` path parameter.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._job_pipeline_helpers import build_scrape_response
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobScrapeResponse
from app.services.job_repository import (
    load_scored_jobs,
    mark_all_jobs_read,
    mark_job_read,
)
from app.services.score_cache import find_cached_score_raw
from app.services.score_selection import select_score, to_score_result
from app.services.text_similarity import comparison_string

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


@router.patch(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all unread jobs as read",
)
async def mark_all_jobs_read_endpoint(
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Set viewed_at = now() on every job where viewed_at IS NULL.

    Idempotent — jobs already read are unaffected.
    """
    count = await mark_all_jobs_read(db)
    logger.info("Marked all jobs as read", extra={"count": count})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{job_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a job as read (sets viewed_at — drives the Unread filter)",
)
async def mark_job_read_endpoint(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Set ``viewed_at = now()`` on the job when the user opens its detail view.

    Idempotent — no-op if the job was already marked as read.
    Leaves ``notified_at`` untouched; that column belongs to the notification system.
    """
    await mark_job_read(db, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{job_id}",
    response_model=JobScrapeResponse,
    summary="Fetch a stored job by ID (used by notification deep-links)",
)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> JobScrapeResponse:
    """Return the full job record for use by the notification deep-link route.

    Reconstructs score fields from the ``job_scores`` row so the frontend's
    ``JobCard`` renders exactly as it did at ingestion time. The active CV's
    score wins; failing that (this job was never scored with the active CV) the
    highest-scoring CV is shown, mirroring the Explorer's priority logic.

    Args:
        job_id: Target job primary key.
        db: Injected async DB session.

    Returns:
        Full :class:`JobScrapeResponse` including scoring fields.

    Raises:
        HTTPException: 404 if no job matches ``job_id``.
    """
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    from app.api.resumes_active import load_active_resume

    active_resume = await load_active_resume(db)
    selected = select_score(
        job.scores, active_resume.id if active_resume is not None else None
    )

    logger.info("Job fetched by ID", extra={"job_id": str(job_id)})
    return build_scrape_response(
        job,
        to_score_result(selected) if selected is not None else None,
        "",
        score_cached=False,
        scored_by_resume_id=selected.resume_id if selected is not None else None,
    )


@router.get(
    "/{job_id}/cached-score",
    summary="Read-only cache check for a (job, resume) pair — no DB writes",
)
async def get_cached_score(
    job_id: UUID,
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Check whether a score is already cached for the given (job, resume) pair.

    No Gemini calls, no blacklist checks, no DB writes of any kind.

    Args:
        job_id: The job's UUID (path parameter).
        resume_id: The resume's UUID (query parameter).
        db: Active async DB session.

    Returns:
        ``{ "cached": false }`` on a miss, or
        ``{ "cached": true, "match_score": int, "rationale": str | null,
        "matched_skills": [...], "missing_skills": [...] }`` on a hit.
    """
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    candidate_raw = job.raw_content or comparison_string(job.job_title, job.job_description)
    scored_jobs = await load_scored_jobs(db, resume_id)
    cached = find_cached_score_raw(candidate_raw, scored_jobs)

    if cached is None:
        return JSONResponse(
            status_code=status.HTTP_200_OK, content={"cached": False}
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "cached": True,
            "match_score": cached.match_score,
            "rationale": cached.rationale,
            "matched_skills": cached.matched_skills,
            "missing_skills": cached.missing_skills,
        },
    )
