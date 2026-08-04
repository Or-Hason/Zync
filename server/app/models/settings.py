from __future__ import annotations

from sqlalchemy import CheckConstraint, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Fixed primary key for the one-and-only settings row (singleton table).
SETTINGS_ROW_ID = 1

# Default scan-configuration values (single source of truth for both the
# upsert-on-first-access defaults and the per-field backfill in the store).
DEFAULT_AUTO_SCAN_ENABLED = False
DEFAULT_SCAN_FREQUENCY_HOURS = 3
DEFAULT_NOTIFICATION_SCORE_THRESHOLD = 80

# Allowed values for scan_frequency_hours (mirrored by the API schema).
SCAN_FREQUENCY_CHOICES = (1, 3, 6, 12, 24)

# Notification-mode defaults.
DEFAULT_NOTIFICATION_MODE = "A"
DEFAULT_DAILY_NOTIFY_TIME = "18:00"
DEFAULT_NOTIFY_IF_ZERO = False
DEFAULT_DND_START = None
DEFAULT_DND_END = None
DEFAULT_IMMEDIATE_JOB_THRESHOLD = 5
DEFAULT_NEXT_SCHEDULED_SCAN_AT = None
DEFAULT_IMMEDIATE_JOBS_FOUND_SINCE_RESET = 0

# Default JSONB payload created on first access.
DEFAULT_SETTINGS_DATA: dict = {
    "blacklist": [],
    "blacklist_bypass_preference": "ask",
    "auto_scan_enabled": DEFAULT_AUTO_SCAN_ENABLED,
    "scan_frequency_hours": DEFAULT_SCAN_FREQUENCY_HOURS,
    "notification_score_threshold": DEFAULT_NOTIFICATION_SCORE_THRESHOLD,
    # Internal scheduler bookkeeping (ISO-8601 string or null); not user-facing.
    "last_scan_at": None,
    # Notification settings.
    "notification_mode": DEFAULT_NOTIFICATION_MODE,
    "daily_notify_time": DEFAULT_DAILY_NOTIFY_TIME,
    "notify_if_zero": DEFAULT_NOTIFY_IF_ZERO,
    "dnd_start": DEFAULT_DND_START,
    "dnd_end": DEFAULT_DND_END,
    "immediate_job_threshold": DEFAULT_IMMEDIATE_JOB_THRESHOLD,
    "next_scheduled_scan_at": DEFAULT_NEXT_SCHEDULED_SCAN_AT,
    "immediate_jobs_found_since_reset": DEFAULT_IMMEDIATE_JOBS_FOUND_SINCE_RESET,
}


class Settings(Base):
    """Singleton row holding all user settings as a flexible JSONB blob.

    A ``CHECK (id = 1)`` constraint enforces that only one row can ever exist,
    so reads and writes always target the same record via upsert.
    """

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint(f"id = {SETTINGS_ROW_ID}", name="ck_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, autoincrement=False, default=SETTINGS_ROW_ID
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
