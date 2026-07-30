"""Notification settings endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.settings import NotificationSettings
from app.scheduler import reset_scheduler_timer
from app.services.settings_store import SettingsStore, get_settings_store

router = APIRouter()
logger = logging.getLogger(__name__)

def _time_in_dnd_window(
    time_str: str, dnd_start: str, dnd_end: str
) -> bool:
    """Check whether ``time_str`` falls inside the DND window.

    Handles windows that span midnight (e.g. 23:00→07:00).

    Args:
        time_str: ``HH:MM`` string to test.
        dnd_start: DND start ``HH:MM``.
        dnd_end: DND end ``HH:MM``.

    Returns:
        ``True`` if ``time_str`` is within the DND window.
    """
    t = int(time_str.replace(":", ""))
    s = int(dnd_start.replace(":", ""))
    e = int(dnd_end.replace(":", ""))
    if s <= e:
        # Same-day window, e.g. 09:00→17:00.
        return s <= t < e
    # Midnight-spanning window, e.g. 23:00→07:00.
    return t >= s or t < e


def _time_to_minutes(time_str: str) -> int:
    """Convert ``HH:MM`` string to total minutes from midnight.

    Args:
        time_str: Time in ``HH:MM`` format.

    Returns:
        Minutes since midnight (0–1439).
    """
    try:
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return 0


def _minutes_to_time(total_min: int) -> str:
    """Convert total minutes to an ``HH:MM`` formatted clock string.

    Args:
        total_min: Minutes, possibly negative or wrapping over 1440.

    Returns:
        Formatted ``HH:MM`` string.
    """
    m = ((total_min % 1440) + 1440) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _calc_auto_dnd_end(start_str: str, daily_notify_str: str | None) -> str:
    """Compute default +8h DND end time, adjusting by -30m if it collides with digest time.

    Args:
        start_str: DND start time in ``HH:MM`` format.
        daily_notify_str: Daily digest notification time in ``HH:MM`` format or ``None``.

    Returns:
        Collision-safe DND end time string in ``HH:MM`` format.
    """
    start_m = _time_to_minutes(start_str)
    end_m = (start_m + 8 * 60) % 1440
    default_end = _minutes_to_time(end_m)
    if daily_notify_str and _time_in_dnd_window(daily_notify_str, start_str, default_end):
        notify_m = _time_to_minutes(daily_notify_str)
        return _minutes_to_time(notify_m - 30)
    return default_end


def _calc_auto_dnd_start(end_str: str, daily_notify_str: str | None) -> str:
    """Compute default -8h DND start time, adjusting by +30m if it collides with digest time.

    Args:
        end_str: DND end time in ``HH:MM`` format.
        daily_notify_str: Daily digest notification time in ``HH:MM`` format or ``None``.

    Returns:
        Collision-safe DND start time string in ``HH:MM`` format.
    """
    end_m = _time_to_minutes(end_str)
    start_m = ((end_m - 8 * 60) % 1440 + 1440) % 1440
    default_start = _minutes_to_time(start_m)
    if daily_notify_str and _time_in_dnd_window(daily_notify_str, default_start, end_str):
        notify_m = _time_to_minutes(daily_notify_str)
        return _minutes_to_time(notify_m + 30)
    return default_start


@router.get(
    "/notifications",
    response_model=NotificationSettings,
    summary="Get notification-mode settings",
)
async def get_notification_settings(
    store: SettingsStore = Depends(get_settings_store),
) -> NotificationSettings:
    """Return the persisted notification-mode configuration."""
    return NotificationSettings(**await store.get_notification_settings())


@router.put(
    "/notifications",
    response_model=NotificationSettings,
    summary="Update notification-mode settings",
)
async def update_notification_settings(
    payload: NotificationSettings,
    store: SettingsStore = Depends(get_settings_store),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettings:
    """Persist the notification-mode configuration.

    Validates that ``daily_notify_time`` does not fall within the DND window.
    After persisting, immediately recalculates ``next_scheduled_scan_at``
    via ``reset_scheduler_timer``.
    
    Raises:
        HTTPException: 400 when ``daily_notify_time`` is inside the DND window.
    """
    # Enforce non-empty defaults for modes B & C
    if payload.notification_mode in ("B", "C") and not payload.daily_notify_time:
        payload.daily_notify_time = "18:00"
    if payload.notification_mode == "C" and not payload.immediate_job_threshold:
        payload.immediate_job_threshold = 5

    # Enforce DND pairing and collision-aware +/- 8 hour window calculation
    notify_time = payload.daily_notify_time or "18:00"
    if payload.notification_mode == "A":
        notify_time = None

    if payload.dnd_start and not payload.dnd_end:
        payload.dnd_end = _calc_auto_dnd_end(payload.dnd_start, notify_time)
    elif payload.dnd_end and not payload.dnd_start:
        payload.dnd_start = _calc_auto_dnd_start(payload.dnd_end, notify_time)
    elif not payload.dnd_start and not payload.dnd_end:
        payload.dnd_start = None
        payload.dnd_end = None

    if (
        payload.notification_mode in ("B", "C")
        and payload.daily_notify_time
        and payload.dnd_start
        and payload.dnd_end
        and _time_in_dnd_window(
            payload.daily_notify_time, payload.dnd_start, payload.dnd_end
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Daily notification time {payload.daily_notify_time} falls "
                f"within the Do Not Disturb window "
                f"({payload.dnd_start}–{payload.dnd_end}). "
                f"Choose a time outside DND hours."
            ),
        )

    updated = await store.update_notification_settings(
        notification_mode=payload.notification_mode,
        daily_notify_time=payload.daily_notify_time,
        notify_if_zero=payload.notify_if_zero,
        dnd_start=payload.dnd_start,
        dnd_end=payload.dnd_end,
        immediate_job_threshold=payload.immediate_job_threshold,
    )
    await reset_scheduler_timer(store)
    await db.commit()
    logger.info(
        "Notification settings updated",
        extra={"notification_mode": updated["notification_mode"]},
    )
    return NotificationSettings(**updated)
