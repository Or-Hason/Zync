"""``POST /jobs/scrape`` — runs the ingestion pipeline and maps its outcome.

Split out of ``jobs.py`` — see ``app/api/jobs.py`` for how these sub-routers are assembled.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._job_pipeline_helpers import build_scrape_outcome_response, resolve_content
from app.db.session import get_db
from app.schemas.job import JobScrapeRequest, JobScrapeResponse
from app.services.gemini_client import GeminiClient, get_gemini_client
from app.services.job_pipeline import rescore_job, run_job_pipeline
from app.services.ollama_client import OllamaClient, get_ollama_client
from app.services.settings_store import SettingsStore, get_settings_store

router = APIRouter(prefix="/jobs", tags=["jobs"])


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

    return build_scrape_outcome_response(outcome)
