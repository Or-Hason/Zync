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
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import ParsedJob, ScoreResult
from app.services.blacklist_filter import find_blacklist_hit
from app.services.duplicate_detection import DuplicateAssessment, detect_duplicate
from app.services.gemini_client import GeminiUnavailableError
from app.services.job_parser import sanitize_job_data
from app.services.job_repository import load_existing_jobs, load_scored_jobs, new_job
from app.services.score_cache import find_cached_score
from app.services.system_advice import LOW_SCORE_THRESHOLD, build_system_advice
from app.services.text_similarity import comparison_string

# Outcome kinds returned by :func:`run_job_pipeline`.
KIND_CLASSIFICATION_REJECTED = "classification_rejected"
KIND_CACHE_HIT = "cache_hit"
KIND_BLACKLISTED = "blacklisted"
KIND_NO_ACTIVE_RESUME = "no_active_resume"
KIND_GEMINI_UNCONFIGURED = "gemini_unconfigured"
KIND_GEMINI_UNAVAILABLE = "gemini_unavailable"
KIND_OLLAMA_PARSE_FAILURE = "ollama_parse_failure"
KIND_SCORED = "scored"


@dataclass
class PipelineOutcome:
    """Structured result of one pipeline run (transport-agnostic).

    Attributes:
        kind: One of the ``KIND_*`` constants describing what happened.
        parsed: The sanitised parsed job (always set once extraction succeeds).
        job: The persisted (or pre-existing) job row, when one is involved.
        score: The score result on a scored run or cache hit.
        advice: The generated ``system_advice`` string when scored/cached.
        score_cached: Whether the score was reused from cache.
        blacklist_keyword: The matched keyword on a blacklist rejection.
    """

    kind: str
    parsed: ParsedJob | None = None
    job: Job | None = None
    score: ScoreResult | None = None
    advice: str | None = None
    score_cached: bool = False
    blacklist_keyword: str | None = None


async def _persist(db: AsyncSession, job: Job) -> None:
    """Add, flush, and refresh a job row so server defaults populate."""
    db.add(job)
    await db.flush()
    await db.refresh(job)


async def run_job_pipeline(
    *,
    db: AsyncSession,
    ollama,
    gemini,
    store,
    content: str,
    source_url: str | None,
    source_type: str = "manual",
    search_filters: dict | None = None,
    force_score: bool = False,
    existing_job_id: UUID | None = None,
    active_resume=None,
) -> PipelineOutcome:
    """Run extraction → classification → dedupe → cache → blacklist → score.

    Args:
        db: Active async DB session.
        ollama: Ollama client (``parse_job`` coroutine).
        gemini: Gemini client (``is_configured`` + ``score`` coroutine).
        store: Settings store (``get_blacklist`` coroutine).
        content: Already-resolved, size-checked job text.
        source_url: Originating URL (``None`` for raw-text ingestion).
        source_type: Ingestion source id (``"manual"`` / ``"jobmaster"``).
        search_filters: Scraper metadata for the ``search_filters`` JSONB column.
        force_score: Bypass blacklist rejection when ``True``.
        existing_job_id: Pre-created row to reuse on the no-active-resume path.
        active_resume: Pre-loaded active resume; loaded lazily when ``None``.

    Returns:
        A :class:`PipelineOutcome` the caller maps to a response or a log entry.
    """
    raw_parse = await ollama.parse_job(content)
    if not raw_parse:
        logger.warning("Ollama returned empty parse after retries — dropping job.")
        return PipelineOutcome(kind=KIND_OLLAMA_PARSE_FAILURE)

    parsed = sanitize_job_data(raw_parse, raw_text=content)

    # Reliable fallback: use raw content when the model omits core_job_posting.
    if not parsed.core_job_posting:
        parsed.core_job_posting = content

    # ── Classification gate: halt before any DB write on junk input ──────────
    classification = parsed.content_classification
    if classification is not None and classification != "VALID_JOB":
        return PipelineOutcome(kind=KIND_CLASSIFICATION_REJECTED, parsed=parsed)

    # Fallback: use inferred_role as title when the posting has no explicit title.
    if not parsed.job_title:
        parsed.job_title = parsed.requirements.inferred_role or "Unknown Title"

    existing_jobs = await load_existing_jobs(db)
    assessment = detect_duplicate(parsed.core_job_posting, existing_jobs)
    candidate_text = comparison_string(parsed.job_title, parsed.job_description)

    if active_resume is None:
        # Imported lazily to avoid a service→api import at module load time.
        from app.api.resumes_active import load_active_resume

        active_resume = await load_active_resume(db)

    # ── Cache check — MUST run before blacklist ──────────────────────────────
    if active_resume is not None:
        scored_jobs = await load_scored_jobs(db, active_resume.id)
        cached = find_cached_score(candidate_text, scored_jobs)
        if cached is not None:
            return await _handle_cache_hit(
                db,
                parsed=parsed,
                cached=cached,
                assessment=assessment,
                source_url=source_url,
                source_type=source_type,
                search_filters=search_filters,
                active_resume_id=active_resume.id,
            )

    # ── Blacklist check ──────────────────────────────────────────────────────
    keyword = find_blacklist_hit(
        parsed.job_title, parsed.job_description, await store.get_blacklist()
    )
    if keyword and not force_score:
        job = new_job(
            parsed,
            raw_content=parsed.core_job_posting,
            source_url=source_url,
            assessment=assessment,
            status="auto_rejected",
            source_type=source_type,
            search_filters=search_filters,
        )
        await _persist(db, job)
        return PipelineOutcome(
            kind=KIND_BLACKLISTED, parsed=parsed, job=job, blacklist_keyword=keyword
        )

    # ── No-active-resume guard ───────────────────────────────────────────────
    if active_resume is None:
        if existing_job_id is not None:
            existing_row = await db.get(Job, existing_job_id)
            if existing_row is not None:
                return PipelineOutcome(
                    kind=KIND_NO_ACTIVE_RESUME, parsed=parsed, job=existing_row
                )
        job = new_job(
            parsed,
            raw_content=parsed.core_job_posting,
            source_url=source_url,
            assessment=assessment,
            status="not_applied",
            source_type=source_type,
            search_filters=search_filters,
        )
        await _persist(db, job)
        return PipelineOutcome(kind=KIND_NO_ACTIVE_RESUME, parsed=parsed, job=job)

    # ── Gemini scoring ───────────────────────────────────────────────────────
    if not gemini.is_configured:
        return PipelineOutcome(kind=KIND_GEMINI_UNCONFIGURED, parsed=parsed)
    try:
        score = await gemini.score(
            parsed.job_title,
            parsed.job_description,
            parsed.requirements.model_dump(),
            active_resume.structured_data,
        )
    except GeminiUnavailableError:
        return PipelineOutcome(kind=KIND_GEMINI_UNAVAILABLE, parsed=parsed)

    if score is not None:
        match_score: int | None = score.match_score
        score_details: dict | None = {
            "rationale": score.rationale,
            "matched_skills": score.matched_skills,
            "missing_skills": score.missing_skills,
        }
        scored_by: UUID | None = active_resume.id
        job_status = (
            "auto_rejected" if match_score < LOW_SCORE_THRESHOLD else "not_applied"
        )
    else:
        match_score = None
        score_details = None
        scored_by = None
        job_status = "not_applied"

    advice = build_system_advice(
        match_score=match_score,
        is_duplicate=assessment.is_duplicate,
        duplicate_chance=assessment.duplicate_chance,
        matched_job_status=assessment.matched_job_status,
    )

    job = new_job(
        parsed,
        raw_content=parsed.core_job_posting,
        source_url=source_url,
        assessment=assessment,
        status=job_status,
        match_score=match_score,
        score_details=score_details,
        scored_by_resume_id=scored_by,
        source_type=source_type,
        search_filters=search_filters,
    )
    await _persist(db, job)
    return PipelineOutcome(
        kind=KIND_SCORED, parsed=parsed, job=job, score=score, advice=advice
    )


async def rescore_job(
    *,
    db: AsyncSession,
    gemini,
    job_id: UUID,
) -> PipelineOutcome:
    """Re-score an existing job with the current active resume. Skips Ollama.

    Resolves to the canonical row (following canonical_job_id if needed), calls
    Gemini with stored job data, creates a child row to preserve rescore history,
    and updates the canonical row's score in-place so the Explorer always shows
    the latest result.
    """
    from uuid import uuid4

    from app.api.resumes_active import load_active_resume

    job = await db.get(Job, job_id)
    if job is None:
        return PipelineOutcome(kind=KIND_GEMINI_UNAVAILABLE)

    # Resolve to canonical — rescoring always operates on the original row.
    canonical = job
    if job.canonical_job_id is not None:
        canonical = await db.get(Job, job.canonical_job_id) or job

    active_resume = await load_active_resume(db)
    if active_resume is None:
        return PipelineOutcome(kind=KIND_NO_ACTIVE_RESUME, job=canonical)

    if not gemini.is_configured:
        return PipelineOutcome(kind=KIND_GEMINI_UNCONFIGURED, job=canonical)

    try:
        score = await gemini.score(
            canonical.job_title,
            canonical.job_description,
            canonical.requirements or {},
            active_resume.structured_data,
        )
    except GeminiUnavailableError:
        return PipelineOutcome(kind=KIND_GEMINI_UNAVAILABLE, job=canonical)

    if score is not None:
        match_score: int | None = score.match_score
        score_details: dict | None = {
            "rationale": score.rationale,
            "matched_skills": score.matched_skills,
            "missing_skills": score.missing_skills,
        }
        new_status = "auto_rejected" if match_score < LOW_SCORE_THRESHOLD else "not_applied"
    else:
        match_score = None
        score_details = None
        new_status = "not_applied"

    # Archive the previous canonical score before overwriting so every CV that
    # has scored this job is preserved as a child row.
    if canonical.scored_by_resume_id is not None and canonical.scored_by_resume_id != active_resume.id:
        archive = Job(
            id=uuid4(),
            company_name=canonical.company_name,
            job_title=canonical.job_title,
            company_description=canonical.company_description,
            job_description=canonical.job_description,
            raw_content=canonical.raw_content,
            requirements=canonical.requirements,
            source_type=canonical.source_type,
            source_url=canonical.source_url,
            match_score=canonical.match_score,
            scored_by_resume_id=canonical.scored_by_resume_id,
            score_details=canonical.score_details,
            status=canonical.status,
            is_duplicate=True,
            duplicate_chance=100,
            published_at=canonical.published_at,
            application_options=canonical.application_options or [],
            recommended_apply_method=canonical.recommended_apply_method,
            canonical_job_id=canonical.id,
        )
        db.add(archive)

    # Update canonical with the latest score.
    if canonical.status in ("not_applied", "auto_rejected"):
        canonical.status = new_status
    canonical.match_score = match_score
    canonical.score_details = score_details
    canonical.scored_by_resume_id = active_resume.id

    await db.flush()
    await db.refresh(canonical)

    advice = build_system_advice(
        match_score=match_score,
        is_duplicate=canonical.is_duplicate,
        duplicate_chance=canonical.duplicate_chance,
        matched_job_status=None,
    )
    return PipelineOutcome(kind=KIND_SCORED, job=canonical, score=score, advice=advice)


async def _handle_cache_hit(
    db: AsyncSession,
    *,
    parsed: ParsedJob,
    cached: ScoreResult,
    assessment: DuplicateAssessment,
    source_url: str | None,
    source_type: str,
    search_filters: dict | None,
    active_resume_id: UUID,
) -> PipelineOutcome:
    """Insert a new row replaying a cached score (no Gemini call).

    A cache hit means near-identical content was already scored — the new row is
    flagged as a duplicate so the UI surfaces the warning, and the cached score
    is replayed verbatim.
    """
    cached_score_details = {
        "rationale": cached.rationale,
        "matched_skills": cached.matched_skills,
        "missing_skills": cached.missing_skills,
    }
    cached_status = (
        "auto_rejected" if cached.match_score < LOW_SCORE_THRESHOLD else "not_applied"
    )
    cached_assessment = DuplicateAssessment(
        is_duplicate=True,
        duplicate_chance=max(assessment.duplicate_chance or 0, 90),
        matched_job_status=assessment.matched_job_status,
    )
    advice = build_system_advice(
        match_score=cached.match_score,
        is_duplicate=True,
        duplicate_chance=cached_assessment.duplicate_chance,
        matched_job_status=assessment.matched_job_status,
    )
    job = new_job(
        parsed,
        raw_content=parsed.core_job_posting,
        source_url=source_url,
        assessment=cached_assessment,
        status=cached_status,
        match_score=cached.match_score,
        score_details=cached_score_details,
        scored_by_resume_id=active_resume_id,
        source_type=source_type,
        search_filters=search_filters,
    )
    await _persist(db, job)
    return PipelineOutcome(
        kind=KIND_CACHE_HIT,
        parsed=parsed,
        job=job,
        score=cached,
        advice=advice,
        score_cached=True,
    )
