"""Pydantic schemas for the cover-letter API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CoverLetterRead(BaseModel):
    """Full cover-letter record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    resume_id: UUID
    original_template_text: str | None
    generated_text: str
    gemini_summary: str | None
    created_at: datetime


class CoverLetterGenerate(BaseModel):
    """Request body for POST cover-letter generation.

    Path and query params supply the identifiers; the body is intentionally
    empty so callers only need to hit the endpoint without crafting a payload.
    """

    pass


class CoverLetterUpdate(BaseModel):
    """Payload for PATCH cover-letter — updates the edited generated text."""

    model_config = ConfigDict(extra="ignore")

    generated_text: str
