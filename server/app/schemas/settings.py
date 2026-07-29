"""Pydantic schemas for the settings API: blacklist, bypass preference, scan, and letter template."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The three blacklist-bypass modes the frontend can persist.
BypassPreference = Literal["ask", "always", "never"]


class BlacklistResponse(BaseModel):
    """Current blacklist keyword list."""

    keywords: list[str]


class KeywordRequest(BaseModel):
    """Payload for adding a blacklist keyword."""

    model_config = ConfigDict(extra="ignore")

    keyword: str = Field(min_length=1)


class BypassPreferenceModel(BaseModel):
    """Read/write payload for the blacklist-bypass preference."""

    model_config = ConfigDict(extra="ignore")

    preference: BypassPreference


# Allowed scan cadences in hours. Mirrors ``SCAN_FREQUENCY_CHOICES`` in
# ``app.models.settings``; using a Literal yields a clean HTTP 422 on bad input.
ScanFrequencyHours = Literal[1, 3, 6, 12, 24]


class LetterTemplateResponse(BaseModel):
    """Current letter template stored in the settings JSONB blob."""

    text: str | None = None
    filename: str | None = None


class LetterTemplateTextUpdate(BaseModel):
    """Payload for PATCH /settings/letter-template — inline text-only save."""

    model_config = ConfigDict(extra="ignore")

    text: str


class ScanSettings(BaseModel):
    """Read/write payload for the auto-scan configuration.

    ``last_scan_at`` and ``scan_in_progress`` are server-managed read-only fields
    returned by GET; they are silently ignored on PUT (``extra="ignore"``).
    """

    model_config = ConfigDict(extra="ignore")

    auto_scan_enabled: bool
    scan_frequency_hours: ScanFrequencyHours
    notification_score_threshold: int = Field(ge=0, le=100)
    last_scan_at: str | None = None
    scan_in_progress: bool = False


# ── Notification settings ─────────────────────────────────────────────────

# Notification delivery strategy: every scan (A), daily digest (B),
# daily + immediate threshold (C).
NotificationMode = Literal["A", "B", "C"]

# HH:MM pattern accepting any valid 24-hour time (00:00–23:59).
HH_MM_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"


class NotificationSettings(BaseModel):
    """Read/write payload for notification-mode configuration.

    Server-managed fields (``next_scheduled_scan_at``,
    ``immediate_jobs_found_since_reset``) are returned by GET but silently
    ignored on PUT via ``extra="ignore"``.
    """

    model_config = ConfigDict(extra="ignore")

    notification_mode: NotificationMode = "A"
    daily_notify_time: str | None = Field(
        default="18:00", pattern=HH_MM_PATTERN
    )
    notify_if_zero: bool = False
    dnd_start: str | None = Field(default=None, pattern=HH_MM_PATTERN)
    dnd_end: str | None = Field(default=None, pattern=HH_MM_PATTERN)
    immediate_job_threshold: int | None = Field(default=5, ge=1, le=20)
    # Read-only server-managed fields.
    next_scheduled_scan_at: str | None = None
    immediate_jobs_found_since_reset: int = 0

