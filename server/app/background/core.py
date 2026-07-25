"""Core scheduler lifecycle (start, stop)."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.settings.store import SettingsStore

from app.background.timer import reset_scheduler_timer
from app.background.tick import scan_tick

logger = logging.getLogger(__name__)

# Base tick cadence in minutes — the scheduler fires frequently so the actual
# scan runs close to the UI's countdown target rather than up to an hour late.
BASE_TICK_MINUTES = 5

_scheduler: AsyncIOScheduler | None = None


async def _init_scheduler_timer() -> None:
    """Initialise ``next_scheduled_scan_at`` on startup.
    
    Opens its own DB session so it can run independently of any request.
    """
    try:
        async with AsyncSessionLocal() as db:
            store = SettingsStore(db)
            await reset_scheduler_timer(store)
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to initialise scheduler timer on startup.")


def start_scheduler() -> None:
    """Start the background scheduler (idempotent).
    
    No-op when ``scheduler_enabled`` is false, so the process-level switch can
    fully disable auto-scan regardless of per-user settings.

    On first start, also kicks off an async task to initialise the
    ``next_scheduled_scan_at`` timestamp from the current notification settings.
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
        minutes=BASE_TICK_MINUTES,
        id="jobmaster_auto_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # Compute the initial next_scheduled_scan_at from persisted settings.
    _scheduler.add_job(
        _init_scheduler_timer,
        trigger="date",
        id="init_scheduler_timer",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Background scheduler started", extra={"tick_minutes": BASE_TICK_MINUTES}
    )


def stop_scheduler() -> None:
    """Stop the background scheduler if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background scheduler stopped")
