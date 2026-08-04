"""JobMaster background scraper."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import notification_bus
from app.services.job_pipeline import KIND_GEMINI_UNAVAILABLE
from app.services.job_repository import count_jobs_for_source, load_known_source_urls
from app.services.job_scraper import JobFetchError, fetch_html
from app.scraper.jobmaster_utils import (
    SCRAPER_SOURCE,
    ScanReport,
    build_search_url,
    extract_job_links,
    select_new_links,
    apply_scan_caps,
)
from app.scraper.jobmaster_process import NotifiableJob, process_link

logger = logging.getLogger(__name__)


async def run_scan(
    *,
    db: AsyncSession,
    ollama,
    gemini,
    store,
    base_url: str,
    initial_limit: int,
    max_per_scan: int,
    notification_threshold: int | None = None,
    is_manual: bool = False,
) -> ScanReport:
    """Run one full JobMaster scan and return a summary report.

    Args:
        db: Active async DB session.
        ollama: Ollama client.
        gemini: Gemini client.
        store: Settings store.
        base_url: JobMaster base URL.
        initial_limit: First-run job cap.
        max_per_scan: Per-scan hard ceiling.
        notification_threshold: Minimum match score to fire a notification.
            ``None`` (default) disables notifications — used by tests and
            any caller that does not want side-effects.

    Returns:
        A :class:`ScanReport` describing what happened.
    """
    # Imported lazily to avoid a scraper→api import at module load time.
    from app.api.resumes_active import load_active_resume

    active_resume = await load_active_resume(db)
    if active_resume is None:
        logger.warning("Scan aborted — no active resume.")
        return ScanReport(aborted_reason="no_active_resume")

    structured = active_resume.structured_data or {}
    target_role = str(structured.get("target_role") or "").strip()
    if not target_role:
        logger.warning("Scan aborted — active resume has no target_role.")
        return ScanReport(aborted_reason="no_target_role")

    search_url = build_search_url(base_url, target_role)
    try:
        html = await fetch_html(search_url)
    except JobFetchError as exc:
        logger.warning("Scan aborted — search fetch failed", extra={"error": str(exc)})
        return ScanReport(aborted_reason="search_fetch_failed")

    discovered = extract_job_links(html, base_url)
    known_urls = await load_known_source_urls(db)
    new_links = select_new_links(discovered, known_urls)

    is_first_run = await count_jobs_for_source(db, SCRAPER_SOURCE) == 0
    to_process = apply_scan_caps(
        new_links,
        is_first_run=is_first_run,
        initial_limit=initial_limit,
        max_per_scan=max_per_scan,
    )

    # Fetch DND settings once before the loop so every qualifying job uses
    # the same snapshot of the DND window for this scan batch.
    notif_cfg = await store.get_notification_settings() if hasattr(store, "get_notification_settings") else {}
    dnd_silent = notification_bus.is_dnd_active(
        notif_cfg.get("dnd_start"), notif_cfg.get("dnd_end")
    )

    processed = 0
    notifiable_jobs: list[NotifiableJob] = []
    for url in to_process:
        kind, notifiable_job = await process_link(
            url,
            db=db,
            ollama=ollama,
            gemini=gemini,
            store=store,
            active_resume=active_resume,
            search_term=target_role,
            is_first_run=is_first_run,
            notification_threshold=notification_threshold,
            is_manual=is_manual,
        )
        if kind == KIND_GEMINI_UNAVAILABLE:
            logger.warning("Scan stopped early — all Gemini models rate-limited.")
            break
        if kind is not None:
            processed += 1
        if notifiable_job is not None:
            notifiable_jobs.append(notifiable_job)
        await asyncio.sleep(1.5)  # pace requests to avoid burst 429s

    # Emit one SSE event per qualifying job now that the full batch count is known.
    job_count = len(notifiable_jobs)
    if job_count > 0:
        mode = notif_cfg.get("notification_mode", "A")
        should_emit = True
        
        # Explicit UI-triggered manual scans ALWAYS bypass background auto-scan notification thresholds.
        if is_manual:
            logger.info("Scan is manual UI-triggered. Bypassing Mode B/C threshold checks.")
        else:
            if mode == "B":
                should_emit = False
            elif mode == "C":
                new_total = await store.increment_immediate_jobs_counter(job_count)
                threshold = int(notif_cfg.get("immediate_job_threshold", 5))
                if new_total >= threshold:
                    job_count = new_total
                    await store.reset_immediate_jobs_counter()
                else:
                    should_emit = False
                
        if should_emit:
            now_utc = datetime.now(timezone.utc)
            for notifiable in notifiable_jobs:
                job = notifiable.job
                await notification_bus.emit_job_match(
                    job_id=str(job.id),
                    job_title=job.job_title or "",
                    match_score=notifiable.match_score,
                    job_count=job_count,
                    silent=dnd_silent,
                )
                job.notified_at = now_utc
            await db.flush()

    logger.info(
        "Scan complete",
        extra={
            "discovered": len(discovered),
            "new_links": len(new_links),
            "processed": processed,
            "first_run": is_first_run,
        },
    )
    return ScanReport(
        discovered=len(discovered),
        new_links=len(new_links),
        processed=processed,
        first_run=is_first_run,
    )
