"""APScheduler-driven background auto-scan loop.

A single ``AsyncIOScheduler`` job fires on a fixed base interval (the smallest
supported scan frequency). On each tick it re-reads the auto-scan configuration
from the DB — so enabling/disabling and frequency changes take effect on the
next tick without a server restart — and only runs the scraper when due.

**Notification modes** control *when* the scheduler fires:

* **Mode A** — frequency-only cadence (``scan_frequency_hours``).
* **Mode B** — daily digest at ``daily_notify_time``; scans run 10 min before.
* **Mode C** — same as B, plus an immediate-threshold override handled by the
  scraper in ``jobmaster.py``.

For B/C, the scheduler maintains a pre-computed ``next_scheduled_scan_at``
timestamp.  ``reset_scheduler_timer`` recalculates it from the saved
``daily_notify_time`` and ``scan_frequency_hours``, ensuring intermediate scans
stay evenly spaced and the final scan fires 10 min before the notification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, time as dt_time, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.scraper.jobmaster import run_scan
from app.services.gemini_client import get_gemini_client
from app.services.ollama_client import get_ollama_client
from app.services.settings_store import SettingsStore

logger = logging.getLogger(__name__)

# Base tick cadence in minutes — the scheduler fires frequently so the actual
# scan runs close to the UI's countdown target rather than up to an hour late.
BASE_TICK_MINUTES = 5

# Slack subtracted from the due threshold so a tick that fires a few seconds shy
# of the exact interval (scheduler jitter) still counts the scan as due.
_DUE_SLACK = timedelta(minutes=5)

# Offset subtracted from daily_notify_time so data is ready when the alert fires.
_SCAN_LEAD_MINUTES = 10

_scheduler: AsyncIOScheduler | None = None


# ── Pure helpers ──────────────────────────────────────────────────────────


def _parse_hhmm(hhmm: str) -> dt_time:
    """Parse a ``HH:MM`` string into a :class:`datetime.time`.

    Args:
        hhmm: Time string in ``HH:MM`` format.

    Returns:
        Parsed :class:`datetime.time` (no tzinfo).
    """
    h, m = hhmm.split(":")
    return dt_time(int(h), int(m))


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


def compute_next_scan_at(
    daily_notify_time: str,
    frequency_hours: int,
    now: datetime,
) -> datetime:
    """Compute the earliest future scan time for modes B/C.

    The final scan of the day fires ``_SCAN_LEAD_MINUTES`` before
    ``daily_notify_time``.  Earlier scans are spaced ``frequency_hours``
    apart, walking backwards from that target.

    If the computed time is already past, advances to tomorrow's window.

    Args:
        daily_notify_time: ``HH:MM`` string.
        frequency_hours: Hours between scans.
        now: Timezone-aware reference timestamp.

    Returns:
        The earliest future scan timestamp (timezone-aware UTC).
    """
    notify_t = _parse_hhmm(daily_notify_time)
    target_dt = datetime.combine(
        now.date(), notify_t, tzinfo=timezone.utc
    ) - timedelta(minutes=_SCAN_LEAD_MINUTES)

    # Walk backwards from the daily target in frequency_hours steps to find
    # the full chain of intermediate scan slots for today.
    slots: list[datetime] = []
    slot = target_dt
    while slot.date() == now.date():
        slots.append(slot)
        slot -= timedelta(hours=frequency_hours)

    # Pick the earliest slot that is still in the future.
    future_slots = [s for s in slots if s > now]
    if future_slots:
        return min(future_slots)

    # All today's slots are in the past — advance the target to tomorrow.
    target_dt += timedelta(days=1)
    slots = []
    slot = target_dt
    tomorrow = target_dt.date()
    while slot.date() == tomorrow:
        slots.append(slot)
        slot -= timedelta(hours=frequency_hours)
    future_slots = [s for s in slots if s > now]
    return min(future_slots) if future_slots else target_dt


# ── Scheduler timer management ────────────────────────────────────────────


async def reset_scheduler_timer(store: SettingsStore) -> None:
    """Recompute ``next_scheduled_scan_at`` from saved settings and persist it.

    Must be called:
    * After ``PUT /api/settings/notifications``
    * On server startup (inside ``start_scheduler``)

    For mode A (or when ``daily_notify_time`` is unset) the field is cleared
    to ``None`` so ``scan_tick`` falls back to frequency-only gating.

    Args:
        store: An active :class:`SettingsStore` instance.
    """
    notif = await store.get_notification_settings()
    mode = notif["notification_mode"]
    daily_time = notif["daily_notify_time"]

    if mode == "A" or not daily_time:
        await store.set_next_scheduled_scan_at(None)
        logger.info(
            "Scheduler timer cleared (mode %s, no daily target).", mode
        )
        return

    scan_cfg = await store.get_scan_settings()
    now = datetime.now(timezone.utc)
    next_at = compute_next_scan_at(
        daily_time, scan_cfg["scan_frequency_hours"], now
    )
    await store.set_next_scheduled_scan_at(next_at.isoformat())
    logger.info(
        "Scheduler timer reset",
        extra={"next_scheduled_scan_at": next_at.isoformat(), "mode": mode},
    )


# ── Tick & lifecycle ──────────────────────────────────────────────────────


async def _run_mode_a_scan(
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


async def _run_mode_bc_scan(
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
        # Timer not yet initialised — recalculate now rather than skipping.
        await reset_scheduler_timer(store)
        return False
    try:
        next_at = datetime.fromisoformat(raw)
    except ValueError:
        await reset_scheduler_timer(store)
        return False
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=timezone.utc)
    return now >= next_at - _DUE_SLACK


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
                should_run = await _run_mode_a_scan(store, scan_cfg, now)
            else:
                should_run = await _run_mode_bc_scan(store, notif_cfg, now)

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

            # For modes B/C, recalculate the next scan timestamp.
            if mode != "A":
                await reset_scheduler_timer(store)

            await db.commit()
    except Exception:  # noqa: BLE001 - a tick must never kill the scheduler.
        logger.exception("Background scan tick failed.")


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
