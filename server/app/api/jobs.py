"""Job ingestion + scoring pipeline: scrape, filter, score, detect duplicates.

Pipeline order: extract -> classification gate -> duplicate detection ->
score cache (early return on hit) -> blacklist filter -> active-resume guard ->
Gemini score -> persist -> auto-reject -> advice.

PII / privacy rule (CLAUDE.md, DESIGN.md): logs reference only ``job_id`` and
``source_type`` — never raw job text, resume PII, or the Gemini API key.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._job_pipeline_helpers import (
    NO_ACTIVE_RESUME_MESSAGE,
    build_scrape_response,
    classification_rejection,
    resolve_content,
)
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobListItem, JobRead, JobScrapeRequest, JobScrapeResponse, ScoreResult
from app.services.gemini_client import GeminiClient, get_gemini_client
from app.services.job_pipeline import (
    KIND_BLACKLISTED,
    KIND_CACHE_HIT,
    KIND_CLASSIFICATION_REJECTED,
    KIND_GEMINI_UNAVAILABLE,
    KIND_GEMINI_UNCONFIGURED,
    KIND_NO_ACTIVE_RESUME,
    KIND_OLLAMA_PARSE_FAILURE,
    rescore_job,
    run_job_pipeline,
)
from app.services.job_repository import (
    get_child_resume_ids,
    list_job_skills,
    list_jobs,
    load_scored_jobs,
    mark_all_jobs_read,
    mark_job_read,
)
from app.services.ollama_client import OllamaClient, get_ollama_client
from app.services.score_cache import find_cached_score_raw
from app.services.settings_store import SettingsStore, get_settings_store
from app.services.text_similarity import comparison_string

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


@router.post(
    "/scrape",
    response_model=JobScrapeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Scrape, filter, score, and persist a job post",
)
async def scrape_job(
    payload: JobScrapeRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    gemini: GeminiClient = Depends(get_gemini_client),
    store: SettingsStore = Depends(get_settings_store),
):
    """Run the full ingestion + scoring pipeline for one job.

    Returns:
        HTTP 200 with the scored job on a cache hit (existing row returned,
        no DB write); HTTP 201 on a fresh score; HTTP 422 on a blacklist hit
        (``force_score`` false); HTTP 400 when no active resume exists.
        502/422 on fetch/size errors; 500 if Gemini is not configured.
    """
    is_rescore_only = (
        payload.existing_job_id is not None
        and payload.url is None
        and not (payload.raw_text and payload.raw_text.strip())
    )

    if is_rescore_only:
        outcome = await rescore_job(db=db, gemini=gemini, job_id=payload.existing_job_id)
    else:
        content = await resolve_content(payload)
        source_url = str(payload.url) if payload.url else None
        outcome = await run_job_pipeline(
            db=db,
            ollama=ollama,
            gemini=gemini,
            store=store,
            content=content,
            source_url=source_url,
            force_score=payload.force_score,
            existing_job_id=payload.existing_job_id,
        )

    if outcome.kind == KIND_OLLAMA_PARSE_FAILURE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI parsing is temporarily unavailable. Please try again shortly.",
        )

    if outcome.kind == KIND_CLASSIFICATION_REJECTED:
        logger.info(
            "Rejected job by content classification",
            extra={"classification": outcome.parsed.content_classification},
        )
        # outcome.parsed is always set on this path; build the 422 response.
        return classification_rejection(outcome.parsed)

    if outcome.kind == KIND_BLACKLISTED:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "blacklist_hit",
                "matched_keyword": outcome.blacklist_keyword,
                "job": jsonable_encoder(JobRead.model_validate(outcome.job)),
            },
        )

    if outcome.kind == KIND_NO_ACTIVE_RESUME:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "no_active_resume",
                "message": NO_ACTIVE_RESUME_MESSAGE,
                "job": jsonable_encoder(JobRead.model_validate(outcome.job)),
            },
        )

    if outcome.kind == KIND_GEMINI_UNCONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gemini API key is not configured.",
        )

    if outcome.kind == KIND_GEMINI_UNAVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="All Gemini models are currently rate-limited. Please try again later.",
        )

    # KIND_CACHE_HIT / KIND_SCORED — a row was persisted with a (cached) score.
    log_message = (
        "Score cache hit — inserted new row"
        if outcome.kind == KIND_CACHE_HIT
        else "Job scored and stored"
    )
    logger.info(
        log_message,
        extra={"job_id": str(outcome.job.id), "source_type": outcome.job.source_type},
    )
    return build_scrape_response(
        outcome.job, outcome.score, outcome.advice, score_cached=outcome.score_cached
    )


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
    skills: list[str] = Query(default_factory=list, description="Required skills (multi)"),
    min_experience: int | None = Query(None, ge=0, description="Minimum years of experience"),
    job_status: str | None = Query(None, alias="status", description="Exact status match"),
    db: AsyncSession = Depends(get_db),
) -> list[JobListItem]:
    """Return up to 200 jobs matching the given filters, newest first.

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
        skills=skills or [],
        min_experience=min_experience,
        status=job_status,
    )

    # Aggregate all resume IDs from child rescore rows.
    parent_ids = [j.id for j in rows]
    child_cv_map = await get_child_resume_ids(db, parent_ids)

    items: list[JobListItem] = []
    for j in rows:
        all_cv_ids = list(
            dict.fromkeys(
                [j.scored_by_resume_id] + child_cv_map.get(j.id, [])
                if j.scored_by_resume_id
                else child_cv_map.get(j.id, [])
            )
        )
        item = JobListItem.model_validate(j).model_copy(
            update={"scored_resume_ids": all_cv_ids}
        )
        items.append(item)

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

    Reconstructs score fields from the persisted ``score_details`` JSONB so the
    frontend's ``JobCard`` renders exactly as it did at ingestion time.

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
    details = job.score_details or {}
    score: ScoreResult | None = None
    if details and job.match_score is not None:
        score = ScoreResult(
            match_score=job.match_score,
            rationale=details.get("rationale"),
            matched_skills=details.get("matched_skills", []),
            missing_skills=details.get("missing_skills", []),
        )
    logger.info("Job fetched by ID", extra={"job_id": str(job_id)})
    return build_scrape_response(job, score, "", score_cached=False)


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
