"""APScheduler-driven background auto-scan loop.

A single ``AsyncIOScheduler`` job fires on a fixed base interval (the smallest
supported scan frequency). On each tick it re-reads the auto-scan configuration
from the DB — so enabling/disabling and frequency changes take effect on the
next tick without a server restart — and only runs the scraper when due.

Cost-safety: the tick is a no-op unless ``auto_scan_enabled`` is true, and the
per-scan job caps live in the scraper itself. The scheduler is never started
during tests (a real, DB-hitting background loop must not run in the suite).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.scraper.jobmaster import run_scan
from app.services.gemini_client import get_gemini_client
from app.services.ollama_client import get_ollama_client
from app.services.settings_store import SettingsStore

logger = logging.getLogger(__name__)

# Base tick cadence in hours — equal to the smallest allowed scan frequency, so
# any configured frequency is an integer multiple of the tick and is honoured by
# the per-tick due-check below.
BASE_TICK_HOURS = 1

# Slack subtracted from the due threshold so a tick that fires a few seconds shy
# of the exact interval (scheduler jitter) still counts the scan as due.
_DUE_SLACK = timedelta(minutes=5)

_scheduler: AsyncIOScheduler | None = None


def is_scan_due(
    last_scan_at_iso: str | None, frequency_hours: int, now: datetime
) -> bool:
    """Whether a scan is due given the last-run time and configured frequency.

    Args:
        last_scan_at_iso: ISO-8601 timestamp of the last scan, or ``None`` if
            none has run yet.
        frequency_hours: Configured hours between scans.
        now: Reference "now" timestamp (timezone-aware).

    Returns:
        ``True`` when no scan has run yet or enough time has elapsed.
    """
    if not last_scan_at_iso:
        return True
    try:
        last = datetime.fromisoformat(last_scan_at_iso)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(hours=frequency_hours) - _DUE_SLACK


async def scan_tick() -> None:
    """One scheduler tick: re-read settings and run the scan when due.

    Swallows and logs all errors so a single bad tick never crashes the loop.
    """
    settings = get_settings()
    try:
        async with AsyncSessionLocal() as db:
            store = SettingsStore(db)
            scan_cfg = await store.get_scan_settings()
            if not scan_cfg["auto_scan_enabled"]:
                return

            if scan_cfg["scan_in_progress"]:
                logger.info("Scan tick skipped — manual scan in progress.")
                return

            now = datetime.now(timezone.utc)
            if not is_scan_due(
                await store.get_last_scan_at(), scan_cfg["scan_frequency_hours"], now
            ):
                return

            try:
                gemini = get_gemini_client()
            except ValueError:
                logger.warning("Scan skipped — Gemini is not configured.")
                return

            await run_scan(
                db=db,
                ollama=get_ollama_client(),
                gemini=gemini,
                store=store,
                base_url=settings.jobmaster_base_url,
                initial_limit=settings.initial_scan_limit,
                max_per_scan=settings.max_jobs_per_scan,
                notification_threshold=scan_cfg["notification_score_threshold"],
            )
            await store.set_last_scan_at(now.isoformat())
            await db.commit()
    except Exception:  # noqa: BLE001 - a tick must never kill the scheduler.
        logger.exception("Background scan tick failed.")


def start_scheduler() -> None:
    """Start the background scheduler (idempotent).

    No-op when ``scheduler_enabled`` is false, so the process-level switch can
    fully disable auto-scan regardless of per-user settings.
    """
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("Background scheduler disabled by configuration.")
        return
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        scan_tick,
        trigger="interval",
        hours=BASE_TICK_HOURS,
        id="jobmaster_auto_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "Background scheduler started", extra={"tick_hours": BASE_TICK_HOURS}
    )


def stop_scheduler() -> None:
    """Stop the background scheduler if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background scheduler stopped")
