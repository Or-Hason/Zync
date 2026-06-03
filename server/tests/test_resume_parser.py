"""Tests for tolerant sanitisation of raw AI output into structured data."""

from __future__ import annotations

from app.services.resume_parser import sanitize_structured_data


class TestSanitizeStructuredData:
    """The sanitiser never raises and always yields the canonical schema."""

    def test_empty_input_yields_all_defaults(self) -> None:
        data = sanitize_structured_data({})
        assert data.full_name is None
        assert data.skills == []
        assert data.experience == []
        assert data.certifications == []

    def test_non_dict_input_yields_defaults(self) -> None:
        data = sanitize_structured_data(["not", "a", "dict"])  # type: ignore[arg-type]
        assert data.full_name is None
        assert data.experience == []

    def test_unexpected_keys_discarded(self) -> None:
        data = sanitize_structured_data({"full_name": "Jane", "hack": "rm -rf /"})
        assert data.full_name == "Jane"
        assert not hasattr(data, "hack")

    def test_numeric_scalars_coerced_to_string(self) -> None:
        data = sanitize_structured_data({"phone": 15551234567})
        assert data.phone == "15551234567"

    def test_blank_strings_become_none(self) -> None:
        data = sanitize_structured_data({"summary": "   "})
        assert data.summary is None

    def test_skill_list_filters_non_strings_and_blanks(self) -> None:
        data = sanitize_structured_data({"skills": ["Python", "", 7, "  Go  ", None]})
        assert data.skills == ["Python", "Go"]

    def test_malformed_experience_items_dropped(self) -> None:
        raw = {
            "experience": [
                {"title": "Engineer", "company": "Acme"},
                "garbage-string",
                42,
                {"title": "Intern"},
            ]
        }
        data = sanitize_structured_data(raw)
        assert len(data.experience) == 2
        assert data.experience[0].title == "Engineer"
        assert data.experience[1].title == "Intern"

    def test_project_technologies_coerced(self) -> None:
        raw = {"projects": [{"name": "Zync", "technologies": ["Py", 1, "React"]}]}
        data = sanitize_structured_data(raw)
        assert data.projects[0].technologies == ["Py", "React"]

    def test_non_list_collection_becomes_empty(self) -> None:
        data = sanitize_structured_data({"skills": "Python, Go"})
        assert data.skills == []


class TestCurrentRoleDerivation:
    """`current_role` is always derived from the most recent experience."""

    def test_prefers_ongoing_entry(self) -> None:
        raw = {
            "current_role": "HALLUCINATED",
            "experience": [
                {"title": "Staff Engineer", "end_date": "Present"},
                {"title": "Senior Engineer", "end_date": "2020"},
            ],
        }
        data = sanitize_structured_data(raw)
        assert data.current_role == "Staff Engineer"

    def test_falls_back_to_first_entry_when_none_ongoing(self) -> None:
        raw = {
            "experience": [
                {"title": "Lead", "end_date": "2023"},
                {"title": "Junior", "end_date": "2019"},
            ]
        }
        data = sanitize_structured_data(raw)
        assert data.current_role == "Lead"

    def test_none_when_no_experience(self) -> None:
        data = sanitize_structured_data({"current_role": "Anything"})
        assert data.current_role is None

    def test_ignores_top_level_value(self) -> None:
        # Even with a top-level current_role, an empty experience list wins.
        data = sanitize_structured_data({"current_role": "CEO", "experience": []})
        assert data.current_role is None
