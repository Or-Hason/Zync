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

import dateparser

from app.schemas.job import JobRequirements, ParsedJob
from app.schemas.skeleton import PLACEHOLDER_SCALAR

# Valid values the LLM is instructed to return for content_classification.
_VALID_CLASSIFICATIONS = frozenset(
    {"VALID_JOB", "LOGIN_WALL", "IRRELEVANT", "INSUFFICIENT_DATA"}
)

# Strips trailing "— חובה", "— יתרון", "— יתרון משמעותי" and English equivalents
# that models append when echoing requirement markers from the source text.
_SKILL_SUFFIX_RE = re.compile(
    r"\s*[—–\-]\s*(?:חובה|יתרון(?:\s+\S+)*|required|mandatory|advantage|preferred|a\s+plus)\s*$",
    re.IGNORECASE,
)



def _is_placeholder(text: str) -> bool:
    """Whether a value is the skeleton placeholder echoed back by the model.

    Smaller local models sometimes copy the schema's ``"string"`` placeholder
    verbatim instead of extracting a real value; such values must be dropped.

    Args:
        text: A trimmed candidate string.

    Returns:
        ``True`` if the value is the placeholder (case-insensitive).
    """
    return text.casefold() == PLACEHOLDER_SCALAR.casefold()


def _as_str(value: Any) -> str | None:
    """Coerce a value to a trimmed non-empty string or ``None``.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        A non-empty string, or ``None`` for blanks / placeholders / unsupported
        types.
    """
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed or _is_placeholder(trimmed):
            return None
        return trimmed
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _as_str_list(value: Any) -> list[str]:
    """Coerce a value into a list of non-empty strings (drops non-strings).

    Args:
        value: Arbitrary value from the model output.

    Returns:
        A list of cleaned strings (empty if the input is not a usable list).
        Placeholder echoes are discarded.
    """
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            trimmed = item.strip()
            if trimmed and not _is_placeholder(trimmed):
                result.append(trimmed)
    return result


def _as_skill_list(value: Any) -> list[str]:
    """Like :func:`_as_str_list` but additionally strips trailing requirement
    markers (e.g. '— חובה', '— יתרון', '— advantage') that models echo from
    the source text.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        A list of stripped, non-empty skill strings.
    """
    items = _as_str_list(value)
    cleaned: list[str] = []
    for item in items:
        cleaned_item = _SKILL_SUFFIX_RE.sub("", item).strip()
        if cleaned_item:
            cleaned.append(cleaned_item)
    return cleaned


def _as_classification(value: Any) -> str | None:
    """Normalise a content_classification value returned by the model.

    Accepts the four expected uppercase strings (case-insensitive to tolerate
    minor model formatting drift). Any unrecognised value is discarded.

    Args:
        value: Arbitrary value from the model output.

    Returns:
        One of the four valid classification strings, or ``None``.
    """
    text = _as_str(value)
    if not text:
        return None
    normalised = text.upper()
    return normalised if normalised in _VALID_CLASSIFICATIONS else None


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

    Delegates to ``dateparser`` which handles absolute dates in many formats
    as well as relative expressions in multiple languages (e.g. Hebrew
    "פורסם לפני 7 שעות", English "3 hours ago").

    Args:
        value: Arbitrary value from the model output.

    Returns:
        An aware datetime, or ``None`` when the value is blank or unparseable.
    """
    text = _as_str(value)
    if not text:
        return None

    return dateparser.parse(
        text,
        settings={
            "RELATIVE_BASE": datetime.now(timezone.utc),
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DAY_OF_MONTH": "first",
        },
    )


def _parse_requirements(value: Any) -> JobRequirements:
    """Coerce the raw ``requirements`` object into a validated model.

    Args:
        value: Arbitrary value from the model output (expected dict).

    Returns:
        A :class:`JobRequirements` with sanitised fields and safe defaults.
    """
    raw = value if isinstance(value, dict) else {}
    return JobRequirements(
        inferred_role=_as_str(raw.get("inferred_role")),
        skills=_as_skill_list(raw.get("skills")),
        recommended_skills=_as_skill_list(raw.get("recommended_skills")),
        years_of_experience=_as_int(raw.get("years_of_experience")),
        education=_as_str(raw.get("education")),
        other=_as_skill_list(raw.get("other")),
        recommended_other=_as_skill_list(raw.get("recommended_other")),
    )


APPLY_METHOD_PLATFORM = "Apply via the platform's native button"
APPLY_METHOD_EMAIL = "Apply via email"
APPLY_METHOD_ATS = "Apply via external ATS link"

_VALID_APPLY_METHODS = frozenset({APPLY_METHOD_PLATFORM, APPLY_METHOD_EMAIL, APPLY_METHOD_ATS})


def _filter_verbatim(options: list[str], raw_text: str) -> list[str]:
    """Keep only options that appear verbatim (case-insensitive) in the source text."""
    text_lower = raw_text.lower()
    return [opt for opt in options if opt.lower() in text_lower]


def _is_valid_apply_option(option: str) -> bool:
    """Return True only for http/https URLs and email addresses.

    Rejects bare job IDs, numbers, or any other non-actionable strings that
    Ollama may hallucinate as application options.
    """
    return option.startswith(("http://", "https://")) or "@" in option


def _as_apply_method(value: Any) -> str:
    """Return the value only when it is one of the three valid method literals."""
    text = _as_str(value)
    return text if text in _VALID_APPLY_METHODS else APPLY_METHOD_PLATFORM


def sanitize_job_data(raw: dict[str, Any], raw_text: str | None = None) -> ParsedJob:
    """Coerce a raw model JSON object into a validated :class:`ParsedJob`.

    Unexpected keys are discarded, missing keys default to ``None`` / ``[]``,
    and malformed values degrade gracefully without raising.

    Args:
        raw: The raw JSON object returned by the AI model.
        raw_text: Original source text used to filter hallucinated application options.

    Returns:
        A fully populated :class:`ParsedJob` instance.
    """
    if not isinstance(raw, dict):
        raw = {}

    app_options = _as_str_list(raw.get("application_options"))
    if raw_text:
        app_options = _filter_verbatim(app_options, raw_text)
    app_options = [opt for opt in app_options if _is_valid_apply_option(opt)]

    return ParsedJob(
        company_name=_as_str(raw.get("company_name")),
        job_title=_as_str(raw.get("job_title")),
        company_description=_as_str(raw.get("company_description")),
        job_description=_as_str(raw.get("job_description")),
        core_job_posting=_as_str(raw.get("core_job_posting")),
        content_classification=_as_classification(raw.get("content_classification")),
        requirements=_parse_requirements(raw.get("requirements")),
        published_at=_parse_published_at(raw.get("published_at")),
        application_options=app_options,
        recommended_apply_method=_as_apply_method(raw.get("recommended_apply_method")),
    )
