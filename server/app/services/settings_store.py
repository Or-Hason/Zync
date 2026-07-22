"""Single-row settings persistence (blacklist + bypass preference).

All settings live in one JSONB blob in the ``settings`` singleton row. The row
is created on first access with a race-condition-safe ``INSERT ... ON CONFLICT``
upsert, so concurrent first reads can never produce duplicate rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.settings import (
    DEFAULT_AUTO_SCAN_ENABLED,
    DEFAULT_DAILY_NOTIFY_TIME,
    DEFAULT_DND_END,
    DEFAULT_DND_START,
    DEFAULT_IMMEDIATE_JOB_THRESHOLD,
    DEFAULT_IMMEDIATE_JOBS_FOUND_SINCE_RESET,
    DEFAULT_NEXT_SCHEDULED_SCAN_AT,
    DEFAULT_NOTIFICATION_MODE,
    DEFAULT_NOTIFICATION_SCORE_THRESHOLD,
    DEFAULT_NOTIFY_IF_ZERO,
    DEFAULT_SCAN_FREQUENCY_HOURS,
    DEFAULT_SETTINGS_DATA,
    SETTINGS_ROW_ID,
    Settings,
)

logger = logging.getLogger(__name__)


class DuplicateKeywordError(Exception):
    """Raised when adding a blacklist keyword that already exists."""


class SettingsStore:
    """Read/write accessor over the singleton settings row."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the store.

        Args:
            db: The active async DB session.
        """
        self._db = db

    async def _load(self) -> dict:
        """Return the settings blob, creating the default row if absent."""
        ensure = (
            insert(Settings)
            .values(id=SETTINGS_ROW_ID, data=dict(DEFAULT_SETTINGS_DATA))
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._db.execute(ensure)
        result = await self._db.execute(
            select(Settings.data).where(Settings.id == SETTINGS_ROW_ID)
        )
        return dict(result.scalar_one())

    async def _save(self, data: dict) -> None:
        """Persist the full settings blob via a race-safe upsert."""
        stmt = (
            insert(Settings)
            .values(id=SETTINGS_ROW_ID, data=data)
            .on_conflict_do_update(index_elements=["id"], set_={"data": data})
        )
        await self._db.execute(stmt)

    async def get_blacklist(self) -> list[str]:
        """Return the current blacklist keywords."""
        data = await self._load()
        return list(data.get("blacklist", []))

    async def add_keyword(self, keyword: str) -> list[str]:
        """Add a trimmed, deduped keyword to the blacklist.

        Args:
            keyword: The keyword to add.

        Returns:
            The updated keyword list.

        Raises:
            ValueError: If the keyword is blank after trimming.
            DuplicateKeywordError: If the keyword already exists (case-insensitive).
        """
        cleaned = keyword.strip()
        if not cleaned:
            raise ValueError("Keyword must not be blank.")

        data = await self._load()
        keywords = list(data.get("blacklist", []))
        if any(cleaned.lower() == existing.lower() for existing in keywords):
            raise DuplicateKeywordError(cleaned)

        keywords.append(cleaned)
        data["blacklist"] = keywords
        await self._save(data)
        return keywords

    async def remove_keyword(self, keyword: str) -> list[str]:
        """Remove a keyword (case-insensitive) from the blacklist.

        Args:
            keyword: The keyword to remove.

        Returns:
            The updated keyword list.
        """
        target = keyword.strip().lower()
        data = await self._load()
        keywords = [k for k in data.get("blacklist", []) if k.lower() != target]
        data["blacklist"] = keywords
        await self._save(data)
        return keywords

    async def get_bypass_preference(self) -> str:
        """Return the blacklist-bypass preference (``ask``/``always``/``never``)."""
        data = await self._load()
        return data.get("blacklist_bypass_preference", "ask")

    async def set_bypass_preference(self, preference: str) -> None:
        """Persist the blacklist-bypass preference.

        Args:
            preference: One of ``ask``, ``always``, ``never``.
        """
        data = await self._load()
        data["blacklist_bypass_preference"] = preference
        await self._save(data)

    async def get_scan_settings(self) -> dict:
        """Return the full auto-scan configuration with defaults backfilled.

        Older settings rows (created before the scan fields existed) lack these
        keys, so each is read with its default to keep reads total.

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
        # When re-enabling auto-scan, reset last_scan_at to now so the countdown
        # starts from a full frequency period instead of showing "Due now" based
        # on a stale timestamp from the previous enable period.
        if auto_scan_enabled and not was_enabled and data.get("last_scan_at"):
            data["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        await self._save(data)
        return await self.get_scan_settings()

    async def set_auto_scan_enabled(self, enabled: bool) -> None:
        """Set only the ``auto_scan_enabled`` flag, leaving other fields intact.

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
        """Record when a scan last ran (scheduler tick-gating bookkeeping).

        Args:
            iso_timestamp: ISO-8601 timestamp string.
        """
        data = await self._load()
        data["last_scan_at"] = iso_timestamp
        await self._save(data)

    # ── Notification settings ──────────────────────────────────────────────────

    async def get_notification_settings(self) -> dict:
        """Return the notification-mode configuration with defaults backfilled.

        Returns:
            Dict with keys: ``notification_mode``, ``daily_notify_time``,
            ``notify_if_zero``, ``dnd_start``, ``dnd_end``,
            ``immediate_job_threshold``, ``next_scheduled_scan_at``,
            ``immediate_jobs_found_since_reset``.
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

        Only user-editable fields are accepted; server-managed fields
        (``next_scheduled_scan_at``, ``immediate_jobs_found_since_reset``)
        are left untouched.

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

    # ── Letter template ───────────────────────────────────────────────────────

    async def get_letter_template(self) -> dict:
        """Return the letter template fields from the settings blob.

        Returns:
            Dict with keys ``letter_template_text`` (str | None) and
            ``letter_template_filename`` (str | None).
        """
        data = await self._load()
        return {
            "text": data.get("letter_template_text"),
            "filename": data.get("letter_template_filename"),
        }

    async def set_letter_template(self, text: str, filename: str) -> dict:
        """Persist the extracted letter template text and original filename.

        Args:
            text: Extracted plain text content of the uploaded file.
            filename: Original filename of the uploaded file.

        Returns:
            The saved template dict with ``text`` and ``filename`` keys.
        """
        data = await self._load()
        data["letter_template_text"] = text
        data["letter_template_filename"] = filename
        await self._save(data)
        return {"text": text, "filename": filename}

    async def update_letter_template_text(self, text: str) -> dict:
        """Update only the template text (inline editor save).

        Args:
            text: The edited template text.

        Returns:
            The updated template dict.
        """
        data = await self._load()
        data["letter_template_text"] = text
        await self._save(data)
        return {"text": text, "filename": data.get("letter_template_filename")}

    async def delete_letter_template(self) -> None:
        """Clear the letter template from the settings blob."""
        data = await self._load()
        data.pop("letter_template_text", None)
        data.pop("letter_template_filename", None)
        await self._save(data)


def get_settings_store(db: AsyncSession = Depends(get_db)) -> SettingsStore:
    """FastAPI dependency providing a :class:`SettingsStore` for the request."""
    return SettingsStore(db)
