"""Job ingestion + scoring pipeline: scrape, filter, score, detect duplicates.

Pipeline order: extract -> duplicate detection -> blacklist filter ->
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
    ParsedJob,
    ScoreResult,
)
from app.services.blacklist_filter import find_blacklist_hit
from app.services.duplicate_detection import detect_duplicate
from app.services.gemini_client import GeminiClient, get_gemini_client
from app.services.job_parser import sanitize_job_data
from app.services.job_repository import (
    load_existing_jobs,
    load_scored_jobs,
    new_job,
    update_job_with_score,
)
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

# Per-classification error codes and user-facing messages returned as HTTP 422.
# None is excluded — an unclassified response is treated as VALID_JOB (lenient).
_CLASSIFICATION_ERRORS: dict[str, tuple[str, str]] = {
    "LOGIN_WALL": (
        "login_wall",
        "This page appears to require a login to view. "
        "Try copying the job posting text and pasting it directly.",
    ),
    "IRRELEVANT": (
        "irrelevant_content",
        "No relevant job details were found in this text. "
        "Please check the content and try a different job posting.",
    ),
    "INSUFFICIENT_DATA": (
        "insufficient_data",
        "The job posting lacks enough details to analyse. "
        "Try including the full job description with requirements and responsibilities.",
    ),
}


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

    # Reliable fallback: use raw content when the model omits core_job_posting.
    if not parsed.core_job_posting:
        parsed.core_job_posting = content

    # ── Classification gate: halt before any DB write on junk input ─────────────
    rejection = _classification_rejection(parsed)
    if rejection is not None:
        logger.info(
            "Rejected job by content classification",
            extra={"classification": parsed.content_classification},
        )
        return rejection

    # Fallback: use inferred_role as title when the posting has no explicit title.
    if not parsed.job_title:
        parsed.job_title = parsed.requirements.inferred_role or "Unknown Title"

    existing = await load_existing_jobs(db)
    assessment = detect_duplicate(parsed.core_job_posting, existing)
    source_url = str(payload.url) if payload.url else None
    candidate_text = comparison_string(parsed.job_title, parsed.job_description)

    # ── Active resume + cache check (runs before blacklist) ───────────────────
    # If a near-identical job was already scored against the current resume, the
    # user has implicitly accepted it; return the cached result immediately so
    # they are never prompted about the blacklist for something already evaluated.
    active_resume = await load_active_resume(db)
    score: ScoreResult | None = None
    score_cached = False

    if active_resume is not None:
        scored_jobs = await load_scored_jobs(db, active_resume.id)
        cached = find_cached_score(candidate_text, scored_jobs)
        if cached is not None:
            score = cached
            score_cached = True

    # ── Blacklist + Gemini (skipped entirely on a cache hit) ──────────────────
    if not score_cached:
        keyword = find_blacklist_hit(
            parsed.job_title, parsed.job_description, await store.get_blacklist()
        )
        if keyword and not payload.force_score:
            job = new_job(
                parsed,
                raw_content=parsed.core_job_posting,
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

        # ── No-active-resume guard ────────────────────────────────────────────
        if active_resume is None:
            job = new_job(
                parsed,
                raw_content=parsed.core_job_posting,
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

        # ── Gemini scoring ────────────────────────────────────────────────────
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

    # ── Persist with score, auto-reject low matches, and advise ──────────────
    if score is not None:
        match_score: int | None = score.match_score
        score_details: dict | None = {
            "rationale": score.rationale,
            "matched_skills": score.matched_skills,
            "missing_skills": score.missing_skills,
        }
        scored_by = active_resume.id if active_resume else None
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
        matched_job_status=assessment.matched_job_status,
    )

    # When the user bypasses a blacklist hit the first request already persisted
    # an auto_rejected row.  Update that row instead of creating a duplicate.
    if payload.existing_job_id is not None:
        job = await update_job_with_score(
            db,
            payload.existing_job_id,
            match_score=match_score,
            score_details=score_details,
            scored_by_resume_id=scored_by,
            status=job_status,
        )
        if job is None:
            job = new_job(
                parsed,
                raw_content=parsed.core_job_posting,
                source_url=source_url,
                assessment=assessment,
                status=job_status,
                match_score=match_score,
                score_details=score_details,
                scored_by_resume_id=scored_by,
            )
            await _persist(db, job)
    else:
        job = new_job(
            parsed,
            raw_content=parsed.core_job_posting,
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


def _classification_rejection(parsed: ParsedJob) -> JSONResponse | None:
    """Return a 422 JSONResponse when the LLM flags the input as non-job content.

    An unclassified response (``None``) is treated as valid to keep the gate
    lenient when the model omits the field. Only explicit non-VALID_JOB values
    halt the pipeline.

    Args:
        parsed: The sanitised parsed job.

    Returns:
        A :class:`JSONResponse` (HTTP 422) for rejected classifications, or
        ``None`` when the pipeline should continue.
    """
    classification = parsed.content_classification
    if classification is None or classification == "VALID_JOB":
        return None
    error_code, message = _CLASSIFICATION_ERRORS.get(
        classification,
        ("irrelevant_content", "No relevant job details were found."),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": error_code, "message": message},
    )


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
