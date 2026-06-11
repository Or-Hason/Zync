"""Pydantic schemas for the settings (blacklist + bypass preference) API."""

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
