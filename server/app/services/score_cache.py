"""Score caching: reuse a prior Gemini score for a near-identical job.

To avoid burning Gemini tokens (and quota) on jobs the user has effectively
already scored, a new job is compared against jobs previously scored *with the
same active resume*. A TF-IDF cosine similarity above the cache threshold means
the prior score and rationale can be replayed verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def find_cached_score(
    candidate_text: str, scored_jobs: list[ScoredJob]
) -> ScoreResult | None:
    """Find a cached score for ``candidate_text`` among already-scored jobs.

    Args:
        candidate_text: The new job's ``title + " " + description`` string.
        scored_jobs: Jobs scored with the same active resume (match_score set).

    Returns:
        A :class:`ScoreResult` rebuilt from the most similar scored job when the
        similarity exceeds :data:`CACHE_SIMILARITY_THRESHOLD`; otherwise
        ``None``.
    """
    if not scored_jobs:
        return None

    match = best_match(candidate_text, [job.comparison_text for job in scored_jobs])
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
