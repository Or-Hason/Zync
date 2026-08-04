"""Notification configuration operations."""

from app.services.settings.base_store import BaseSettingsStore
from app.models.settings import (
    DEFAULT_NOTIFICATION_MODE,
    DEFAULT_DAILY_NOTIFY_TIME,
    DEFAULT_NOTIFY_IF_ZERO,
    DEFAULT_DND_START,
    DEFAULT_DND_END,
    DEFAULT_IMMEDIATE_JOB_THRESHOLD,
    DEFAULT_NEXT_SCHEDULED_SCAN_AT,
    DEFAULT_IMMEDIATE_JOBS_FOUND_SINCE_RESET,
)

class NotificationMixin(BaseSettingsStore):
    """Mixin for notification-mode settings and state."""

    async def get_notification_settings(self) -> dict:
        """Return the notification-mode configuration with defaults backfilled.

        Returns:
            Dict with notification settings keys.
        """
        data = await self._load()
        return {
            "notification_mode": data.get(
                "notification_mode", DEFAULT_NOTIFICATION_MODE
            ),
            "daily_notify_time": data.get(
                "daily_notify_time", DEFAULT_DAILY_NOTIFY_TIME
            ),
            "notify_if_zero": bool(
                data.get("notify_if_zero", DEFAULT_NOTIFY_IF_ZERO)
            ),
            "dnd_start": data.get("dnd_start", DEFAULT_DND_START),
            "dnd_end": data.get("dnd_end", DEFAULT_DND_END),
            "immediate_job_threshold": data.get(
                "immediate_job_threshold", DEFAULT_IMMEDIATE_JOB_THRESHOLD
            ),
            "next_scheduled_scan_at": data.get(
                "next_scheduled_scan_at", DEFAULT_NEXT_SCHEDULED_SCAN_AT
            ),
            "immediate_jobs_found_since_reset": int(
                data.get(
                    "immediate_jobs_found_since_reset",
                    DEFAULT_IMMEDIATE_JOBS_FOUND_SINCE_RESET,
                )
            ),
        }

    async def update_notification_settings(
        self,
        *,
        notification_mode: str,
        daily_notify_time: str | None,
        notify_if_zero: bool,
        dnd_start: str | None,
        dnd_end: str | None,
        immediate_job_threshold: int | None,
    ) -> dict:
        """Persist the notification-mode configuration.

        Args:
            notification_mode: One of ``A``, ``B``, ``C``.
            daily_notify_time: ``HH:MM`` string (15-min step) or ``None``.
            notify_if_zero: Whether to notify even when 0 jobs were found.
            dnd_start: DND window start ``HH:MM`` or ``None``.
            dnd_end: DND window end ``HH:MM`` or ``None``.
            immediate_job_threshold: Mode-C job count threshold or ``None``.

        Returns:
            The full notification-settings dict after save.
        """
        data = await self._load()
        data["notification_mode"] = notification_mode
        data["daily_notify_time"] = daily_notify_time
        data["notify_if_zero"] = notify_if_zero
        data["dnd_start"] = dnd_start
        data["dnd_end"] = dnd_end
        data["immediate_job_threshold"] = immediate_job_threshold
        await self._save(data)
        return await self.get_notification_settings()

    async def set_next_scheduled_scan_at(
        self, iso_timestamp: str | None
    ) -> None:
        """Persist the next-scan timestamp computed by the scheduler.

        Args:
            iso_timestamp: ISO-8601 timestamp or ``None`` to clear.
        """
        data = await self._load()
        data["next_scheduled_scan_at"] = iso_timestamp
        await self._save(data)

    async def increment_immediate_jobs_counter(self, count: int) -> int:
        """Add to the Mode C counter and return the new total.
        
        Args:
            count: Number of qualifying jobs to add.
        Returns:
            The new counter value.
        """
        data = await self._load()
        current = int(data.get("immediate_jobs_found_since_reset", 0))
        new_total = current + count
        data["immediate_jobs_found_since_reset"] = new_total
        await self._save(data)
        return new_total

    async def reset_immediate_jobs_counter(self) -> None:
        """Reset the Mode C counter to zero."""
        data = await self._load()
        data["immediate_jobs_found_since_reset"] = 0
        await self._save(data)
