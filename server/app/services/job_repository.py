"""Persistence helpers for the job scrape/score pipeline.

Keeps the ORM construction and the read projections (duplicate scan, score
cache) out of the endpoint so it stays focused on HTTP orchestration.

Facade: the implementation lives in ``app/services/job_repository_parts/``
(ORM construction, pipeline read projections, the Explorer query, and
read/unread mutations). Re-exported here so
``from app.services.job_repository import ...`` keeps working.
"""

from app.services.job_repository_parts.explorer_query import list_jobs
from app.services.job_repository_parts.pipeline_reads import (
    DUPLICATE_SCAN_LIMIT,
    count_jobs_for_source,
    load_existing_jobs,
    load_known_source_urls,
    load_scored_jobs,
)
from app.services.job_repository_parts.read_state import (
    list_job_skills,
    mark_all_jobs_read,
    mark_job_read,
)
from app.services.job_repository_parts.writes import (
    new_job,
    new_job_score,
    upsert_job_score,
)

__all__ = [
    "DUPLICATE_SCAN_LIMIT",
    "new_job",
    "new_job_score",
    "upsert_job_score",
    "load_existing_jobs",
    "load_scored_jobs",
    "load_known_source_urls",
    "count_jobs_for_source",
    "list_jobs",
    "mark_all_jobs_read",
    "mark_job_read",
    "list_job_skills",
]
