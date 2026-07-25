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
    if (
        payload.daily_notify_time
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
