"""Private helpers for the job ingestion pipeline endpoint.

Extracted from ``jobs.py``.
These functions are intentionally prefixed with ``_`` — they are not part of the
public API surface and should only be called from ``jobs.py``.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.models.job import Job
from app.schemas.job import (
    JobRead,
    JobScrapeRequest,
    JobScrapeResponse,
    ParsedJob,
    ScoreResult,
)
from app.services.job_pipeline import (
    KIND_BLACKLISTED,
    KIND_CACHE_HIT,
    KIND_CLASSIFICATION_REJECTED,
    KIND_GEMINI_UNAVAILABLE,
    KIND_GEMINI_UNCONFIGURED,
    KIND_NO_ACTIVE_RESUME,
    KIND_OLLAMA_PARSE_FAILURE,
    PipelineOutcome,
)
from app.services.job_scraper import (
    ContentTooLargeError,
    JobFetchError,
    enforce_content_size,
    extract_content,
    fetch_html,
)

logger = logging.getLogger(__name__)

NO_ACTIVE_RESUME_MESSAGE = (
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


def classification_rejection(parsed: ParsedJob) -> JSONResponse | None:
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


def build_scrape_response(
    job: Job,
    score: ScoreResult | None,
    advice: str,
    score_cached: bool,
    scored_by_resume_id: UUID | None = None,
) -> JobScrapeResponse:
    """Assemble the full scrape+score response payload.

    ``match_score`` / ``scored_by_resume_id`` are injected from the scoring
    result rather than read off the job row — a job has one score per CV, stored
    in ``job_scores``, and this response describes exactly one of them.

    Args:
        job: The persisted job row.
        score: The score result (or ``None`` when scoring failed).
        advice: The generated ``system_advice`` string.
        score_cached: Whether the score was reused from cache.
        scored_by_resume_id: The resume ``score`` was computed against.

    Returns:
        The :class:`JobScrapeResponse`.
    """
    base = JobRead.model_validate(job).model_dump()
    base["match_score"] = score.match_score if score else None
    base["scored_by_resume_id"] = scored_by_resume_id if score else None
    return JobScrapeResponse(
        **base,
        rationale=score.rationale if score else None,
        matched_skills=score.matched_skills if score else [],
        missing_skills=score.missing_skills if score else [],
        system_advice=advice,
        score_cached=score_cached,
    )


async def resolve_content(payload: JobScrapeRequest) -> str:
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


def build_scrape_outcome_response(
    outcome: PipelineOutcome,
) -> JSONResponse | JobScrapeResponse | None:
    """Map a pipeline outcome to the ``POST /jobs/scrape`` HTTP response.

    Extracted from the endpoint body so ``jobs.py`` stays focused on request
    wiring; this is the exact outcome→HTTP-response ladder that used to live
    inline in ``scrape_job``.

    Args:
        outcome: The result of :func:`run_job_pipeline` or :func:`rescore_job`.

    Returns:
        The response for the endpoint to return.

    Raises:
        HTTPException: On the Ollama-unavailable, Gemini-unconfigured, and
            Gemini-unavailable outcomes.
    """
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
        outcome.job,
        outcome.score,
        outcome.advice,
        score_cached=outcome.score_cached,
        scored_by_resume_id=outcome.scored_by_resume_id,
    )
