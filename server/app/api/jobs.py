"""Job ingestion endpoint: scrape/parse a posting and detect duplicates.

PII / privacy rule (CLAUDE.md, DESIGN.md): logs reference only ``job_id`` and
``source_type`` — never the raw job text, extracted descriptions, or source URL.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobRead, JobScrapeRequest
from app.services.duplicate_detection import ExistingJob, detect_duplicate
from app.services.job_parser import sanitize_job_data
from app.services.job_scraper import (
    ContentTooLargeError,
    JobFetchError,
    enforce_content_size,
    extract_content,
    fetch_html,
)
from app.services.ollama_client import OllamaClient, get_ollama_client

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

# Cap on existing rows pulled into memory for duplicate comparison.
_DUPLICATE_SCAN_LIMIT = 500


@router.post(
    "/scrape",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Scrape or ingest a job post, parse it, and detect duplicates",
)
async def scrape_job(
    payload: JobScrapeRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
) -> JobRead:
    """Ingest a job from a URL or raw text, parse it, and persist it.

    Args:
        payload: Validated request carrying ``url`` or ``raw_text`` (and the
            ``force_score`` pass-through flag).
        db: Injected async DB session.
        ollama: Injected async Ollama client.

    Returns:
        The created job record (HTTP 201).

    Raises:
        HTTPException: 422 if extracted content exceeds the size cap; 502 if a
            URL could not be fetched.
    """
    content = await _resolve_content(payload)

    raw_extracted = await ollama.parse_job(content)
    parsed = sanitize_job_data(raw_extracted)

    existing = await _load_existing_jobs(db)
    assessment = detect_duplicate(parsed.job_title, parsed.job_description, existing)

    job = Job(
        id=uuid4(),
        company_name=parsed.company_name,
        job_title=parsed.job_title,
        company_description=parsed.company_description,
        job_description=parsed.job_description,
        requirements=parsed.requirements.model_dump(),
        source_type="manual",
        source_url=str(payload.url) if payload.url else None,
        status="not_applied",
        is_duplicate=assessment.is_duplicate,
        duplicate_chance=assessment.duplicate_chance,
        published_at=parsed.published_at,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    logger.info(
        "Job scraped and stored",
        extra={"job_id": str(job.id), "source_type": job.source_type},
    )
    return JobRead.model_validate(job)


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
            html = await fetch_html(str(payload.url))
            return extract_content(html)

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


async def _load_existing_jobs(db: AsyncSession) -> list[ExistingJob]:
    """Load a capped, lightweight projection of existing jobs for comparison.

    Selects only the columns needed for TF-IDF comparison — never full rows —
    ordered newest-first and capped at :data:`_DUPLICATE_SCAN_LIMIT`.

    Args:
        db: Injected async DB session.

    Returns:
        A list of :class:`ExistingJob` projections.
    """
    stmt = (
        select(Job.job_title, Job.job_description, Job.created_at)
        .order_by(Job.created_at.desc())
        .limit(_DUPLICATE_SCAN_LIMIT)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ExistingJob(
            job_title=row.job_title,
            job_description=row.job_description,
            created_at=row.created_at,
        )
        for row in rows
    ]
