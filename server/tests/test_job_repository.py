"""Tests for job_repository.new_job field mapping (source_type, search_filters)."""

from __future__ import annotations

from app.schemas.job import ParsedJob
from app.services.duplicate_detection import DuplicateAssessment
from app.services.job_repository import new_job

_ASSESSMENT = DuplicateAssessment(is_duplicate=False, duplicate_chance=0)


def _parsed() -> ParsedJob:
    return ParsedJob(job_title="Backend Engineer", job_description="Build APIs.")


class TestNewJobSourceMetadata:
    """new_job stamps the scraper source and search_filters onto the row."""

    def test_defaults_to_manual_without_search_filters(self) -> None:
        job = new_job(
            _parsed(),
            raw_content="text",
            source_url=None,
            assessment=_ASSESSMENT,
            status="not_applied",
        )
        assert job.source_type == "manual"
        assert job.search_filters is None

    def test_scraper_source_and_search_filters_persisted(self) -> None:
        search_filters = {
            "source": "jobmaster",
            "search_term": "Backend",
            "scraped_at": "2026-06-10T12:00:00+00:00",
            "initial_run": True,
        }
        job = new_job(
            _parsed(),
            raw_content="text",
            source_url="https://www.jobmaster.co.il/code/kot/click.asp?i=1",
            assessment=_ASSESSMENT,
            status="not_applied",
            source_type="jobmaster",
            search_filters=search_filters,
        )
        assert job.source_type == "jobmaster"
        assert job.search_filters == search_filters
        assert job.source_url.endswith("i=1")
