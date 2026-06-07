"""Score caching: reuse a prior Gemini score for a near-identical job.

To avoid burning Gemini tokens (and quota) on jobs the user has effectively
already scored, a new job is compared against jobs previously scored *with the
same active resume*. A TF-IDF cosine similarity above the cache threshold means
the prior score and rationale can be replayed verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.schemas.job import ScoreResult
from app.services.text_similarity import best_match

# Similarity strictly above this against an already-scored job is a cache hit.
CACHE_SIMILARITY_THRESHOLD = 0.90


@dataclass(frozen=True)
class ScoredJob:
    """An already-scored job available for cache reuse."""

    comparison_text: str
    match_score: int
    score_details: dict | None
    job_id: UUID
    raw_content: str | None = None


def find_cache_hit(
    candidate_text: str, scored_jobs: list[ScoredJob]
) -> tuple[ScoreResult, UUID] | None:
    """Find a cached score and return both the score and the source job's ID.

    Args:
        candidate_text: The new job's ``title + " " + description`` string.
        scored_jobs: Jobs scored with the same active resume (match_score set).

    Returns:
        A ``(ScoreResult, job_id)`` tuple on cache hit, or ``None``.
    """
    if not scored_jobs:
        return None

    match = best_match(candidate_text, [job.comparison_text for job in scored_jobs])
    if match is None or match.score <= CACHE_SIMILARITY_THRESHOLD:
        return None

    job = scored_jobs[match.index]
    details = job.score_details or {}
    score = ScoreResult(
        match_score=job.match_score,
        rationale=details.get("rationale"),
        matched_skills=details.get("matched_skills") or [],
        missing_skills=details.get("missing_skills") or [],
    )
    return score, job.job_id


def find_cached_score_raw(
    candidate_raw: str, scored_jobs: list[ScoredJob]
) -> ScoreResult | None:
    """Cache check using raw_content instead of title+description.

    Used by the read-only GET endpoint to avoid false misses caused by
    TF-IDF non-transitivity across Ollama extraction runs. Raw content is
    larger and more stable text, so similarity scores are more consistent.

    Args:
        candidate_raw: The queried job's ``raw_content``.
        scored_jobs: Jobs scored with the target resume (``raw_content`` set).

    Returns:
        A :class:`ScoreResult` on cache hit, or ``None``.
    """
    if not candidate_raw or not scored_jobs:
        return None

    corpus = [sj.raw_content or sj.comparison_text for sj in scored_jobs]
    match = best_match(candidate_raw, corpus)
    if match is None or match.score <= CACHE_SIMILARITY_THRESHOLD:
        return None

    job = scored_jobs[match.index]
    details = job.score_details or {}
    return ScoreResult(
        match_score=job.match_score,
        rationale=details.get("rationale"),
        matched_skills=details.get("matched_skills") or [],
        missing_skills=details.get("missing_skills") or [],
    )


def find_cached_score(
    candidate_text: str, scored_jobs: list[ScoredJob]
) -> ScoreResult | None:
    """Return only the cached :class:`ScoreResult`, or ``None`` on miss.

    Thin wrapper around :func:`find_cache_hit` for callers that do not need
    the source job ID (e.g. the read-only cache-check endpoint).

    Args:
        candidate_text: The new job's ``title + " " + description`` string.
        scored_jobs: Jobs scored with the same active resume (match_score set).

    Returns:
        A :class:`ScoreResult` on cache hit, or ``None``.
    """
    hit = find_cache_hit(candidate_text, scored_jobs)
    return hit[0] if hit is not None else None
