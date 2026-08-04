"""Reusable core of the job ingestion + scoring pipeline.

Both the HTTP endpoint (``POST /api/jobs/scrape``) and the background scraper run
the *same* logic through :func:`run_job_pipeline`, so scoring, caching, blacklist
filtering, and duplicate detection behave identically regardless of entry point
(single source of truth — no duplicated pipeline logic).

The function never raises ``HTTPException`` or returns an HTTP response: it takes
already-resolved job text and returns a structured :class:`PipelineOutcome`. The
caller translates that outcome into an HTTP response (endpoint) or a log + future
notification hook (scraper).

PII / privacy rule: this module logs nothing containing raw job text or resume
PII — callers log only ``job_id`` and ``source_type``.

Facade: the implementation lives in ``app/services/job_pipeline_parts/``
(outcome types/constants, the ingestion path, and the re-score path).
Re-exported here so ``from app.services.job_pipeline import ...`` keeps working.
"""

from app.services.job_pipeline_parts.ingest import run_job_pipeline
from app.services.job_pipeline_parts.outcomes import (
    KIND_BLACKLISTED,
    KIND_CACHE_HIT,
    KIND_CLASSIFICATION_REJECTED,
    KIND_GEMINI_UNAVAILABLE,
    KIND_GEMINI_UNCONFIGURED,
    KIND_NO_ACTIVE_RESUME,
    KIND_OLLAMA_PARSE_FAILURE,
    KIND_SCORED,
    PipelineOutcome,
)
from app.services.job_pipeline_parts.rescore import rescore_job

__all__ = [
    "run_job_pipeline",
    "rescore_job",
    "PipelineOutcome",
    "KIND_SCORED",
    "KIND_CACHE_HIT",
    "KIND_BLACKLISTED",
    "KIND_CLASSIFICATION_REJECTED",
    "KIND_GEMINI_UNAVAILABLE",
    "KIND_GEMINI_UNCONFIGURED",
    "KIND_NO_ACTIVE_RESUME",
    "KIND_OLLAMA_PARSE_FAILURE",
]
