"""Tests for resilient sanitisation of raw Ollama job output."""

from __future__ import annotations

from datetime import datetime

from app.services.job_parser import sanitize_job_data

_VALID_RAW = {
    "company_name": "Acme Corp",
    "job_title": "Senior Backend Engineer",
    "company_description": "We build logistics software.",
    "job_description": "Own the async API platform.",
    "requirements": {
        "skills": ["Python", "", "FastAPI", 7],
        "years_of_experience": "5+ years",
        "education": "B.Sc. Computer Science",
        "other": ["On-call rotation", 42],
    },
    "published_at": "2026-05-01",
    "unexpected_key": "discard me",
}


class TestValidExtraction:
    """A well-formed payload is fully populated and cleaned."""

    def test_top_level_fields(self) -> None:
        parsed = sanitize_job_data(_VALID_RAW)
        assert parsed.company_name == "Acme Corp"
        assert parsed.job_title == "Senior Backend Engineer"
        assert parsed.company_description == "We build logistics software."
        assert parsed.job_description == "Own the async API platform."

    def test_requirements_are_sanitised(self) -> None:
        parsed = sanitize_job_data(_VALID_RAW)
        # Non-string skills are dropped; "5+ years" -> 5.
        assert parsed.requirements.skills == ["Python", "FastAPI"]
        assert parsed.requirements.years_of_experience == 5
        assert parsed.requirements.education == "B.Sc. Computer Science"
        assert parsed.requirements.other == ["On-call rotation"]

    def test_new_requirement_fields(self) -> None:
        parsed = sanitize_job_data(
            {
                "requirements": {
                    "inferred_role": "Full Stack Developer",
                    "recommended_skills": ["Angular", "DDS"],
                }
            }
        )
        assert parsed.requirements.inferred_role == "Full Stack Developer"
        assert parsed.requirements.recommended_skills == ["Angular", "DDS"]

    def test_core_job_posting_verbatim_copied(self) -> None:
        text = "Senior Python Engineer\n\nBuild our async API platform using FastAPI."
        parsed = sanitize_job_data({"core_job_posting": text})
        assert parsed.core_job_posting == text

    def test_core_job_posting_placeholder_dropped(self) -> None:
        parsed = sanitize_job_data({"core_job_posting": "string"})
        assert parsed.core_job_posting is None

    def test_content_classification_valid_values(self) -> None:
        for val in ("VALID_JOB", "LOGIN_WALL", "IRRELEVANT", "INSUFFICIENT_DATA"):
            parsed = sanitize_job_data({"content_classification": val})
            assert parsed.content_classification == val

    def test_content_classification_case_normalised(self) -> None:
        parsed = sanitize_job_data({"content_classification": "valid_job"})
        assert parsed.content_classification == "VALID_JOB"

    def test_content_classification_unknown_becomes_none(self) -> None:
        parsed = sanitize_job_data({"content_classification": "NONSENSE"})
        assert parsed.content_classification is None


class TestPlaceholderEchoIsDropped:
    """Skeleton placeholders echoed back by the model are discarded."""

    def test_scalar_placeholder_becomes_none(self) -> None:
        parsed = sanitize_job_data(
            {"company_name": "string", "job_title": "String", "education": "string"}
        )
        assert parsed.company_name is None
        assert parsed.job_title is None
        assert parsed.requirements.education is None

    def test_placeholder_filtered_from_lists(self) -> None:
        parsed = sanitize_job_data(
            {"requirements": {"skills": ["Python", "string", "FastAPI"]}}
        )
        assert parsed.requirements.skills == ["Python", "FastAPI"]

    def test_published_at_is_parsed(self) -> None:
        parsed = sanitize_job_data(_VALID_RAW)
        assert isinstance(parsed.published_at, datetime)
        assert parsed.published_at.year == 2026
        assert parsed.published_at.month == 5
        assert parsed.published_at.day == 1
        # Naive dates are assumed UTC.
        assert parsed.published_at.tzinfo is not None


class TestPublishedAtFormats:
    """Lenient date parsing across common formats."""

    def test_iso_with_time(self) -> None:
        parsed = sanitize_job_data({"published_at": "2026-03-15T09:30:00"})
        assert parsed.published_at is not None
        assert parsed.published_at.month == 3

    def test_long_month_format(self) -> None:
        parsed = sanitize_job_data({"published_at": "May 1, 2026"})
        assert parsed.published_at is not None
        assert parsed.published_at.day == 1

    def test_unrecognised_format_is_none(self) -> None:
        parsed = sanitize_job_data({"published_at": "xyz-notadate-abc"})
        assert parsed.published_at is None

    def test_relative_date_is_parsed(self) -> None:
        parsed = sanitize_job_data({"published_at": "3 hours ago"})
        assert parsed.published_at is not None
        assert parsed.published_at.tzinfo is not None

    def test_blank_is_none(self) -> None:
        assert sanitize_job_data({"published_at": "  "}).published_at is None


class TestMalformedInput:
    """Partial / malformed payloads degrade to defaults without raising."""

    def test_non_dict_input(self) -> None:
        parsed = sanitize_job_data("not a dict")  # type: ignore[arg-type]
        assert parsed.company_name is None
        assert parsed.requirements.skills == []
        assert parsed.requirements.years_of_experience is None

    def test_empty_dict_defaults(self) -> None:
        parsed = sanitize_job_data({})
        assert parsed.job_title is None
        assert parsed.job_description is None
        assert parsed.requirements.education is None
        assert parsed.requirements.other == []
        assert parsed.published_at is None

    def test_requirements_not_a_dict(self) -> None:
        parsed = sanitize_job_data({"requirements": ["nope"]})
        assert parsed.requirements.skills == []
        assert parsed.requirements.years_of_experience is None

    def test_numeric_years_passthrough(self) -> None:
        assert sanitize_job_data(
            {"requirements": {"years_of_experience": 3}}
        ).requirements.years_of_experience == 3
