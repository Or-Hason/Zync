"""Scan configuration operations."""

from datetime import datetime, timezone
from app.services.settings.base_store import BaseSettingsStore
from app.models.settings import (
    DEFAULT_AUTO_SCAN_ENABLED,
    DEFAULT_SCAN_FREQUENCY_HOURS,
    DEFAULT_NOTIFICATION_SCORE_THRESHOLD,
)

class ScanMixin(BaseSettingsStore):
    """Mixin for scan configuration and state tracking."""

    async def get_scan_settings(self) -> dict:
        """Return the full auto-scan configuration with defaults backfilled.

        Returns:
            Dict with keys: ``auto_scan_enabled``, ``scan_frequency_hours``,
            ``notification_score_threshold``, ``last_scan_at``, ``scan_in_progress``.
        """
        data = await self._load()
        raw_last = data.get("last_scan_at")
        return {
            "auto_scan_enabled": bool(
                data.get("auto_scan_enabled", DEFAULT_AUTO_SCAN_ENABLED)
            ),
            "scan_frequency_hours": int(
                data.get("scan_frequency_hours", DEFAULT_SCAN_FREQUENCY_HOURS)
            ),
            "notification_score_threshold": int(
                data.get(
                    "notification_score_threshold",
                    DEFAULT_NOTIFICATION_SCORE_THRESHOLD,
                )
            ),
            "last_scan_at": raw_last if isinstance(raw_last, str) else None,
            "scan_in_progress": bool(data.get("scan_in_progress", False)),
        }

    async def update_scan_settings(
        self,
        *,
        auto_scan_enabled: bool,
        scan_frequency_hours: int,
        notification_score_threshold: int,
    ) -> dict:
        """Persist all three auto-scan configuration fields.

        Args:
            auto_scan_enabled: Whether background scanning is on.
            scan_frequency_hours: Hours between scans (validated by the schema).
            notification_score_threshold: Minimum score (0–100) to notify on.

        Returns:
            The updated scan-settings dict.
        """
        data = await self._load()
        was_enabled = bool(data.get("auto_scan_enabled", DEFAULT_AUTO_SCAN_ENABLED))
        data["auto_scan_enabled"] = bool(auto_scan_enabled)
        data["scan_frequency_hours"] = int(scan_frequency_hours)
        data["notification_score_threshold"] = int(notification_score_threshold)
        
        if auto_scan_enabled and not was_enabled and data.get("last_scan_at"):
            data["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        await self._save(data)
        return await self.get_scan_settings()

    async def set_auto_scan_enabled(self, enabled: bool) -> None:
        """Set only the ``auto_scan_enabled`` flag.
        
        Used by the resume-deletion guard, which must disable auto-scan inside
        the same transaction as the deletion.
        Args:
            enabled: The new flag value.
        """
        data = await self._load()
        data["auto_scan_enabled"] = bool(enabled)
        await self._save(data)

    async def get_scan_in_progress(self) -> bool:
        """Return whether a scan is currently executing."""
        data = await self._load()
        return bool(data.get("scan_in_progress", False))

    async def set_scan_in_progress(self, in_progress: bool) -> None:
        """Set the scan-in-progress flag.
        
        Args:
            in_progress: ``True`` when a scan has started; ``False`` when done.
        """
        data = await self._load()
        data["scan_in_progress"] = bool(in_progress)
        await self._save(data)

    async def get_last_scan_at(self) -> str | None:
        """Return the ISO-8601 timestamp of the last completed scan, or ``None``."""
        data = await self._load()
        value = data.get("last_scan_at")
        return value if isinstance(value, str) else None

    async def set_last_scan_at(self, iso_timestamp: str) -> None:
        """Record when a scan last ran.

        Args:
            iso_timestamp: ISO-8601 timestamp string.
        """
        data = await self._load()
        data["last_scan_at"] = iso_timestamp
        await self._save(data)
