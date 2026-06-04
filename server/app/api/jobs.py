"""Job ingestion + scoring pipeline: scrape, filter, score, detect duplicates.

Pipeline order: extract (BE-03) -> duplicate detection -> blacklist filter ->
active-resume guard -> score cache -> Gemini score -> auto-reject -> advice.

PII / privacy rule (CLAUDE.md, DESIGN.md): logs reference only ``job_id`` and
``source_type`` — never raw job text, resume PII, or the Gemini API key.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resumes_active import load_active_resume
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import (
    JobRead,
    JobScrapeRequest,
    JobScrapeResponse,
    ScoreResult,
)
from app.services.blacklist_filter import find_blacklist_hit
from app.services.duplicate_detection import detect_duplicate
from app.services.gemini_client import GeminiClient, get_gemini_client
from app.services.job_parser import sanitize_job_data
from app.services.job_repository import load_existing_jobs, load_scored_jobs, new_job
from app.services.job_scraper import (
    ContentTooLargeError,
    JobFetchError,
    enforce_content_size,
    extract_content,
    fetch_html,
)
from app.services.ollama_client import OllamaClient, get_ollama_client
from app.services.score_cache import find_cached_score
from app.services.settings_store import SettingsStore, get_settings_store
from app.services.system_advice import LOW_SCORE_THRESHOLD, build_system_advice
from app.services.text_similarity import comparison_string

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

_NO_ACTIVE_RESUME_MESSAGE = (
    "No active resume selected. Please upload or select a resume to enable scoring."
)


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
        HTTP 201 with the scored job (:class:`JobScrapeResponse`) on success;
        HTTP 422 on a blacklist hit (``force_score`` false); HTTP 400 when no
        active resume exists. 502/422 on fetch/size errors; 500 if Gemini is
        not configured and a fresh score is required.
    """
    content = await _resolve_content(payload)

    parsed = sanitize_job_data(await ollama.parse_job(content))
    existing = await load_existing_jobs(db)
    assessment = detect_duplicate(parsed.job_title, parsed.job_description, existing)
    source_url = str(payload.url) if payload.url else None

    # ── Blacklist filtration (scans title + description only) ─────────────────
    keyword = find_blacklist_hit(
        parsed.job_title, parsed.job_description, await store.get_blacklist()
    )
    if keyword and not payload.force_score:
        job = new_job(
            parsed,
            source_url=source_url,
            assessment=assessment,
            status="auto_rejected",
        )
        await _persist(db, job)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "blacklist_hit",
                "matched_keyword": keyword,
                "job": jsonable_encoder(JobRead.model_validate(job)),
            },
        )

    # ── No-active-resume guard ────────────────────────────────────────────────
    active_resume = await load_active_resume(db)
    if active_resume is None:
        job = new_job(
            parsed,
            source_url=source_url,
            assessment=assessment,
            status="not_applied",
        )
        await _persist(db, job)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "no_active_resume",
                "message": _NO_ACTIVE_RESUME_MESSAGE,
                "job": jsonable_encoder(JobRead.model_validate(job)),
            },
        )

    # ── Score: cache hit, else Gemini ─────────────────────────────────────────
    candidate_text = comparison_string(parsed.job_title, parsed.job_description)
    scored_jobs = await load_scored_jobs(db, active_resume.id)
    cached = find_cached_score(candidate_text, scored_jobs)
    if cached is not None:
        score: ScoreResult | None = cached
        score_cached = True
    else:
        if not gemini.is_configured:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gemini API key is not configured.",
            )
        score = await gemini.score(
            parsed.job_title,
            parsed.job_description,
            parsed.requirements.model_dump(),
            active_resume.structured_data,
        )
        score_cached = False

    # ── Persist with score, auto-reject low matches, and advise ──────────────
    if score is not None:
        match_score: int | None = score.match_score
        score_details: dict | None = {
            "rationale": score.rationale,
            "matched_skills": score.matched_skills,
            "missing_skills": score.missing_skills,
        }
        scored_by = active_resume.id
        job_status = (
            "auto_rejected" if match_score < LOW_SCORE_THRESHOLD else "not_applied"
        )
    else:
        match_score = None
        score_details = None
        scored_by = None
        job_status = "not_applied"

    advice = build_system_advice(
        match_score=match_score,
        is_duplicate=assessment.is_duplicate,
        duplicate_chance=assessment.duplicate_chance,
    )

    job = new_job(
        parsed,
        source_url=source_url,
        assessment=assessment,
        status=job_status,
        match_score=match_score,
        score_details=score_details,
        scored_by_resume_id=scored_by,
    )
    await _persist(db, job)

    logger.info(
        "Job scored and stored",
        extra={"job_id": str(job.id), "source_type": job.source_type},
    )
    return _build_response(job, score, advice, score_cached)


def _build_response(
    job: Job, score: ScoreResult | None, advice: str, score_cached: bool
) -> JobScrapeResponse:
    """Assemble the full scrape+score response payload.

    Args:
        job: The persisted job row.
        score: The score result (or ``None`` when scoring failed).
        advice: The generated ``system_advice`` string.
        score_cached: Whether the score was reused from cache.

    Returns:
        The :class:`JobScrapeResponse`.
    """
    base = JobRead.model_validate(job).model_dump()
    return JobScrapeResponse(
        **base,
        rationale=score.rationale if score else None,
        matched_skills=score.matched_skills if score else [],
        missing_skills=score.missing_skills if score else [],
        system_advice=advice,
        score_cached=score_cached,
    )


async def _persist(db: AsyncSession, job: Job) -> None:
    """Add, flush, and refresh a job row so server defaults are populated."""
    db.add(job)
    await db.flush()
    await db.refresh(job)


async def _resolve_content(payload: JobScrapeRequest) -> str:
    """Resolve the job text from either the URL or the raw_text source.

    Args:
        payload: The validated scrape request.

    Returns:
        The extracted, size-checked job text.

    Raises:
        HTTPException: 502 on fetch failure; 422 on oversized content.
    """
    try:
        if payload.url is not None:
            return extract_content(await fetch_html(str(payload.url)))

        content = (payload.raw_text or "").strip()
        enforce_content_size(content)
        return content
    except JobFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch the provided job URL.",
        ) from exc
    except ContentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
