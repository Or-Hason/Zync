"""Sanitise raw AI output into a validated :class:`ResumeStructuredData`.

The model output is untrusted: it may contain missing keys, wrong types, extra
keys, or malformed array items. Every value is coerced into the canonical schema
without raising, so a partial response degrades gracefully to defaults rather
than crashing the upload endpoint.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.resume import (
    EducationEntry,
    ExperienceEntry,
    LanguageEntry,
    ProjectEntry,
    ResumeStructuredData,
    VolunteeringEntry,
)

# end_date values that mark an experience entry as the candidate's current role.
_CURRENT_MARKERS = frozenset({"", "present", "current", "now", "ongoing", "today"})


def _as_str(value: Any) -> str | None:
    """Coerce a value to a trimmed non-empty string or ``None``.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        A non-empty string, or ``None`` for blanks / unsupported types.
    """
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _as_str_list(value: Any) -> list[str]:
    """Coerce a value into a list of non-empty strings.

    Only genuine strings are kept; numeric or structural items in a string list
    (e.g. skills, certifications) are treated as noise and dropped.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        A list of cleaned strings (empty if the input is not a usable list).
    """
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            trimmed = item.strip()
            if trimmed:
                result.append(trimmed)
    return result


def _as_entry_list(value: Any, model: type[BaseModel]) -> list[Any]:
    """Coerce a value into a list of validated entry models, dropping bad items.

    Args:
        value: Arbitrary value from the model output.
        model: The Pydantic entry model to validate each item against.

    Returns:
        A list of validated model instances (malformed items are skipped).
    """
    if not isinstance(value, list):
        return []
    result: list[Any] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            result.append(model.model_validate(item))
        except ValidationError:
            continue
    return result


def _derive_current_role(experience: list[ExperienceEntry]) -> str | None:
    """Infer ``current_role`` from the most recent experience entry.

    Prefers an entry whose ``end_date`` marks it as ongoing; otherwise falls
    back to the first (newest-first ordered) entry's title.

    Args:
        experience: Sanitised experience entries.

    Returns:
        The inferred current role title, or ``None`` when unavailable.
    """
    if not experience:
        return None
    for entry in experience:
        end_date = (entry.end_date or "").strip().lower()
        if end_date in _CURRENT_MARKERS and entry.title:
            return entry.title
    return experience[0].title


def sanitize_structured_data(raw: dict[str, Any]) -> ResumeStructuredData:
    """Coerce a raw model JSON object into a validated structured-data model.

    Unexpected keys are discarded, missing keys default to ``None`` / ``[]``,
    malformed array items are dropped, and ``current_role`` is recomputed from
    the experience entries so it never reflects a hallucinated top-level value.

    Args:
        raw: The raw JSON object returned by the AI model.

    Returns:
        A fully populated :class:`ResumeStructuredData` instance.
    """
    if not isinstance(raw, dict):
        raw = {}

    experience = _as_entry_list(raw.get("experience"), ExperienceEntry)

    return ResumeStructuredData(
        full_name=_as_str(raw.get("full_name")),
        current_role=_derive_current_role(experience),
        target_role=_as_str(raw.get("target_role")),
        email=_as_str(raw.get("email")),
        phone=_as_str(raw.get("phone")),
        location=_as_str(raw.get("location")),
        linkedin_url=_as_str(raw.get("linkedin_url")),
        github_url=_as_str(raw.get("github_url")),
        portfolio_url=_as_str(raw.get("portfolio_url")),
        summary=_as_str(raw.get("summary")),
        skills=_as_str_list(raw.get("skills")),
        experience=experience,
        education=_as_entry_list(raw.get("education"), EducationEntry),
        projects=_as_entry_list(raw.get("projects"), ProjectEntry),
        volunteering=_as_entry_list(raw.get("volunteering"), VolunteeringEntry),
        languages=_as_entry_list(raw.get("languages"), LanguageEntry),
        certifications=_as_str_list(raw.get("certifications")),
    )
