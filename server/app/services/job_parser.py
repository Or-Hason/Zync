"""Sanitise raw Ollama job output into a validated :class:`ParsedJob`.

Mirrors the resilient, never-raising approach of the resume parser: missing or
malformed keys degrade to ``null`` / ``[]`` defaults so a partial model response
can never crash the scrape endpoint. ``published_at`` is parsed leniently from
common date string formats into an aware datetime, or ``None`` when unrecognised.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.schemas.job import JobRequirements, ParsedJob

# Accepted ``published_at`` formats, tried after a lenient ISO-8601 parse.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


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
    """Coerce a value into a list of non-empty strings (drops non-strings).

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


def _as_int(value: Any) -> int | None:
    """Coerce a value into a non-negative integer years-of-experience.

    Tolerates strings such as ``"5"`` or ``"5+ years"`` by extracting the first
    integer found.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        The parsed integer, or ``None`` when no usable value is present.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        return int(match.group()) if match else None
    return None


def _parse_published_at(value: Any) -> datetime | None:
    """Parse a model-supplied date string into a timezone-aware datetime.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        An aware datetime (UTC assumed when no offset is given), or ``None``
        when the value is blank or in an unrecognised format.
    """
    text = _as_str(value)
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_requirements(value: Any) -> JobRequirements:
    """Coerce the raw ``requirements`` object into a validated model.

    Args:
        value: Arbitrary value from the model output (expected dict).

    Returns:
        A :class:`JobRequirements` with sanitised fields and safe defaults.
    """
    raw = value if isinstance(value, dict) else {}
    return JobRequirements(
        skills=_as_str_list(raw.get("skills")),
        years_of_experience=_as_int(raw.get("years_of_experience")),
        education=_as_str(raw.get("education")),
        other=_as_str_list(raw.get("other")),
    )


def sanitize_job_data(raw: dict[str, Any]) -> ParsedJob:
    """Coerce a raw model JSON object into a validated :class:`ParsedJob`.

    Unexpected keys are discarded, missing keys default to ``None`` / ``[]``,
    and malformed values degrade gracefully without raising.

    Args:
        raw: The raw JSON object returned by the AI model.

    Returns:
        A fully populated :class:`ParsedJob` instance.
    """
    if not isinstance(raw, dict):
        raw = {}

    return ParsedJob(
        company_name=_as_str(raw.get("company_name")),
        job_title=_as_str(raw.get("job_title")),
        company_description=_as_str(raw.get("company_description")),
        job_description=_as_str(raw.get("job_description")),
        requirements=_parse_requirements(raw.get("requirements")),
        published_at=_parse_published_at(raw.get("published_at")),
    )
