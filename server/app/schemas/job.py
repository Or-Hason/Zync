"""Pydantic schemas for the job scrape endpoint and AI job extraction.

`ParsedJob` is the single source of truth for the structured fields Ollama must
extract: it drives both the prompt skeleton (so keys are never hardcoded twice)
and the sanitised result persisted to the ``jobs`` row. Every field defaults to
``None`` / ``[]`` so a partial or malformed model response degrades gracefully
rather than raising.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class JobRequirements(BaseModel):
    """Structured requirements extracted from a job post."""

    model_config = ConfigDict(extra="ignore")

    skills: list[str] = Field(default_factory=list)
    years_of_experience: int | None = None
    education: str | None = None
    other: list[str] = Field(default_factory=list)


class ParsedJob(BaseModel):
    """Canonical structured representation of a parsed job post.

    Doubles as the AI prompt skeleton source. ``published_at`` is typed as a
    datetime for storage; the prompt skeleton renders it as a ``"string"``
    placeholder, matching the string date the model is asked to return.
    """

    model_config = ConfigDict(extra="ignore")

    company_name: str | None = None
    job_title: str | None = None
    company_description: str | None = None
    job_description: str | None = None
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    published_at: datetime | None = None


class JobScrapeRequest(BaseModel):
    """Request body for ``POST /api/jobs/scrape``.

    Exactly one ingestion source is required: a ``url`` to fetch and scrape, or
    pre-extracted ``raw_text``. ``force_score`` is passed through to the
    downstream scoring pipeline (BE-04) to bypass blacklist rejection.
    """

    model_config = ConfigDict(extra="ignore")

    url: HttpUrl | None = None
    raw_text: str | None = None
    force_score: bool = False

    @model_validator(mode="after")
    def _require_source(self) -> "JobScrapeRequest":
        """Reject requests carrying neither a URL nor non-empty raw text.

        Returns:
            The validated request.

        Raises:
            ValueError: If both ``url`` and ``raw_text`` are absent/blank
                (surfaced by FastAPI as HTTP 422).
        """
        if self.url is None and not (self.raw_text and self.raw_text.strip()):
            raise ValueError("Either 'url' or 'raw_text' must be provided.")
        return self


class JobRead(BaseModel):
    """Full job record returned by the scrape endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str | None
    job_title: str | None
    company_description: str | None
    job_description: str | None
    requirements: JobRequirements | None
    source_type: str
    source_url: str | None
    match_score: int | None
    status: str
    is_duplicate: bool
    duplicate_chance: int | None
    scored_by_resume_id: UUID | None
    published_at: datetime | None
    created_at: datetime


class ScoreResult(BaseModel):
    """Validated match-scoring output from Gemini (or a cache hit)."""

    model_config = ConfigDict(extra="ignore")

    match_score: int
    rationale: str | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class JobScrapeResponse(JobRead):
    """Full scrape + score payload returned on a successful pipeline run.

    Extends :class:`JobRead` with the scoring fields the frontend needs to
    render the Job Card — present even for auto-rejected jobs so the card can
    still show the score and rationale.
    """

    rationale: str | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    system_advice: str | None = None
    score_cached: bool = False
