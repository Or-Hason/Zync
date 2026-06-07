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
