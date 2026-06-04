"""Pydantic schemas for resume parsing and the resume API.

`ResumeStructuredData` (and its nested entry models) is the single source of
truth for the shape of ``resumes.structured_data``. The Ollama prompt skeleton,
response sanitisation, and API responses all derive from these models so the
field set is never duplicated by hand.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.skeleton import build_model_skeleton


def _clean_str_list(value: Any) -> Any:
    """Keep only non-empty string items in a list (drops numeric/noise items).

    Args:
        value: Candidate value for a ``list[str]`` field.

    Returns:
        A cleaned list when given a list; the original value otherwise (so
        Pydantic still reports a type error for genuinely wrong inputs).
    """
    if not isinstance(value, list):
        return value
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]

# ── Nested structured_data entries ───────────────────────────────────────────


class ExperienceEntry(BaseModel):
    """A single employment history entry."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class EducationEntry(BaseModel):
    """A single education history entry."""

    model_config = ConfigDict(extra="ignore")

    degree: str | None = None
    institution: str | None = None
    graduation_year: str | None = None


class ProjectEntry(BaseModel):
    """A single project entry."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)

    @field_validator("technologies", mode="before")
    @classmethod
    def _coerce_technologies(cls, value: Any) -> Any:
        """Drop non-string technology items instead of failing validation."""
        return _clean_str_list(value)


class VolunteeringEntry(BaseModel):
    """A single volunteering entry."""

    model_config = ConfigDict(extra="ignore")

    organization: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class LanguageEntry(BaseModel):
    """A spoken/written language with self-reported proficiency."""

    model_config = ConfigDict(extra="ignore")

    language: str | None = None
    proficiency_level: str | None = None


class ResumeStructuredData(BaseModel):
    """Canonical structured representation of a parsed resume.

    Every field defaults to ``None`` / ``[]`` so a partial or malformed AI
    response can always be coerced into a valid object without raising.
    """

    model_config = ConfigDict(extra="ignore")

    full_name: str | None = None
    current_role: str | None = None
    target_role: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    volunteering: list[VolunteeringEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


# ── API request / response schemas ───────────────────────────────────────────


class ResumeRead(BaseModel):
    """Full resume record returned by upload and update endpoints.

    Deliberately omits ``raw_text`` and ``file_path``: raw resume text is PII
    and the on-disk path is an internal detail.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_name: str
    target_role: str | None
    structured_data: ResumeStructuredData | None
    created_at: datetime


class ResumeListItem(BaseModel):
    """Lightweight resume summary for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_name: str
    target_role: str | None
    created_at: datetime


class ActiveResumeResponse(BaseModel):
    """The currently active resume, as needed by the scoring pipeline / UI."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_name: str
    structured_data: ResumeStructuredData | None


class ResumeUpdate(BaseModel):
    """Partial update payload for ``PUT /api/resumes/{id}``."""

    model_config = ConfigDict(extra="ignore")

    version_name: str | None = None
    structured_data: ResumeStructuredData | None = None


# ── Prompt skeleton generation ───────────────────────────────────────────────


def build_structured_data_skeleton() -> dict[str, Any]:
    """Return a JSON skeleton of :class:`ResumeStructuredData` for the AI prompt.

    Returns:
        A dict mirroring the structured-data schema, with ``"string"`` /
        nested placeholders, generated from the model so keys are never
        hardcoded twice.
    """
    return build_model_skeleton(ResumeStructuredData)
