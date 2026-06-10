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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._job_pipeline_helpers import (
    NO_ACTIVE_RESUME_MESSAGE,
    build_scrape_response,
    classification_rejection,
    resolve_content,
)
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobRead, JobScrapeRequest, JobScrapeResponse
from app.services.gemini_client import GeminiClient, get_gemini_client
from app.services.job_pipeline import (
    KIND_BLACKLISTED,
    KIND_CACHE_HIT,
    KIND_CLASSIFICATION_REJECTED,
    KIND_GEMINI_UNAVAILABLE,
    KIND_GEMINI_UNCONFIGURED,
    KIND_NO_ACTIVE_RESUME,
    run_job_pipeline,
)
from app.services.job_repository import load_scored_jobs
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
