"""Job page fetching and pipeline execution logic."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_pipeline import KIND_CACHE_HIT, KIND_SCORED, run_job_pipeline
from app.services.job_scraper import ContentTooLargeError, JobFetchError, extract_content, fetch_html
from app.scraper.jobmaster_utils import SCRAPER_SOURCE

logger = logging.getLogger(__name__)


async def process_link(
    url: str,
    *,
    db: AsyncSession,
    ollama,
    gemini,
    store,
    active_resume,
    search_term: str,
    is_first_run: bool,
    notification_threshold: int | None = None,
    is_manual: bool = False,
) -> tuple[str | None, object | None]:
    """Fetch one job page and run it through the scoring pipeline.
    
    Args:
        url: Absolute job-posting URL.
        db: Active async DB session.
        ollama: Ollama client.
        gemini: Gemini client.
        store: Settings store.
        active_resume: The active resume (passed through to avoid re-loading).
        search_term: The role searched for (stamped into search_filters).
        is_first_run: Whether this scan is the source's first run.
        notification_threshold: Minimum match score to emit a notification.
            ``None`` disables notification (safe default for tests / manual runs).

    Returns:
        A ``(kind, notifiable_job)`` tuple. ``kind`` is the pipeline outcome
        string (or ``None`` when the page could not be fetched/extracted).
        ``notifiable_job`` is the job ORM object when it qualifies for a
        notification, otherwise ``None``.
    """
    try:
        content = extract_content(await fetch_html(url))
    except (JobFetchError, ContentTooLargeError) as exc:
        logger.warning("Skipping job — fetch/extract failed", extra={"error": str(exc)})
        return None, None

    search_filters = {
        "source": SCRAPER_SOURCE,
        "search_term": search_term,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "initial_run": is_first_run,
    }
    outcome = await run_job_pipeline(
        db=db,
        ollama=ollama,
        gemini=gemini,
        store=store,
        content=content,
        source_url=url,
        source_type=SCRAPER_SOURCE,
        search_filters=search_filters,
        active_resume=active_resume,
    )
    if outcome.job is not None:
        logger.info(
            "Scraper processed job",
            extra={"job_id": str(outcome.job.id), "source_type": SCRAPER_SOURCE},
        )

    # Mark jobs that qualify for notification; the actual emit happens in
    # run_scan after all links are processed so the full batch job_count is known.
    notifiable_job = None
    if (
        notification_threshold is not None
        and outcome.kind in (KIND_SCORED, KIND_CACHE_HIT)
        and outcome.job is not None
        and outcome.job.match_score is not None
        and outcome.job.notified_at is None
        and outcome.job.match_score >= notification_threshold
    ):
        notifiable_job = outcome.job

    return outcome.kind, notifiable_job
