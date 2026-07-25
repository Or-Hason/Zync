"""Timer management for the scheduler."""

import logging
from datetime import datetime, timezone

from app.services.settings.store import SettingsStore
from app.background.time_utils import compute_next_scan_at

logger = logging.getLogger(__name__)

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
