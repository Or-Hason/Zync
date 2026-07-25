"""Tick and execution logic for the background scheduler."""

import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.scraper.jobmaster import run_scan
from app.services.gemini_client import get_gemini_client
from app.services.ollama_client import get_ollama_client
from app.services.settings.store import SettingsStore

from app.background.time_utils import is_scan_due, DUE_SLACK
from app.background.timer import reset_scheduler_timer

logger = logging.getLogger(__name__)


async def run_mode_a_scan(
    store: SettingsStore,
    scan_cfg: dict,
    now: datetime,
) -> bool:
    """Return ``True`` if a Mode-A scan is due.
    
    Args:
        store: Settings store.
        scan_cfg: Scan configuration dict.
        now: Current UTC datetime.

    Returns:
        Whether the scan should run.
    """
    return is_scan_due(
        await store.get_last_scan_at(),
        scan_cfg["scan_frequency_hours"],
        now,
    )


async def run_mode_bc_scan(
    store: SettingsStore,
    notif_cfg: dict,
    now: datetime,
) -> bool:
    """Return ``True`` if a Mode-B/C scan is due based on next_scheduled_scan_at.
    
    After the scan runs, ``scan_tick`` is responsible for recalculating the
    next timestamp via ``reset_scheduler_timer``.

    Args:
        store: Settings store.
        notif_cfg: Notification configuration dict.
        now: Current UTC datetime.

    Returns:
        Whether the scan should run.
    """
    raw = notif_cfg.get("next_scheduled_scan_at")
    if not raw:
        await reset_scheduler_timer(store)
        return False
    try:
        next_at = datetime.fromisoformat(raw)
    except ValueError:
        await reset_scheduler_timer(store)
        return False
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=timezone.utc)
    return now >= next_at - DUE_SLACK


async def scan_tick() -> None:
    """One scheduler tick: re-read settings and run the scan when due.
    
    Dispatches to Mode A (frequency-only) or Mode B/C (daily target) based
    on the persisted ``notification_mode``.  Swallows and logs all errors so
    a single bad tick never crashes the loop.
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
            notif_cfg = await store.get_notification_settings()
            mode = notif_cfg["notification_mode"]

            if mode == "A":
                should_run = await run_mode_a_scan(store, scan_cfg, now)
            else:
                should_run = await run_mode_bc_scan(store, notif_cfg, now)

            if not should_run:
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

            if mode != "A":
                await reset_scheduler_timer(store)

            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Background scan tick failed.")
