"""Private helpers for the job ingestion pipeline endpoint.

Extracted from ``jobs.py`` to keep the router module under the 300-LOC limit.
These functions are intentionally prefixed with ``_`` — they are not part of the
public API surface and should only be called from ``jobs.py``.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.models.job import Job
from app.schemas.job import (
    JobRead,
    JobScrapeRequest,
    JobScrapeResponse,
    ParsedJob,
    ScoreResult,
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
