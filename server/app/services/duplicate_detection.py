"""Content-based duplicate detection via title-weighted TF-IDF cosine similarity.

Each job is reduced to a single comparison string of
``job_title + " " + job_description``. Because the title is present in every
vector it is naturally weighted into the similarity score without a separate
weighting term. A new job is compared against recent existing jobs and
classified with time-decay rules: a strong match against a recent post is a true
duplicate, while the same match against an old post is flagged only as a
re-application candidate (not an outright duplicate).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.text_similarity import best_match, comparison_string

# Re-exported under the historical private name so BE-03 tests keep working.
_comparison_string = comparison_string

# Cosine similarity strictly above this is considered a strong content match.
SIMILARITY_THRESHOLD = 0.75
# A strong match against a post newer than this window is a true duplicate;
# older than this it is only a re-application candidate.
RECENCY_WINDOW = timedelta(days=183)
# Floor applied to duplicate_chance for a confirmed (recent) duplicate.
DUPLICATE_CHANCE_FLOOR = 85


@dataclass(frozen=True)
class ExistingJob:
    """Minimal projection of an existing job row used for comparison."""

    job_title: str | None
    job_description: str | None
    created_at: datetime


@dataclass(frozen=True)
class DuplicateAssessment:
    """Outcome of duplicate detection for a candidate job."""

    is_duplicate: bool
    duplicate_chance: int


def _is_recent(created_at: datetime | None, now: datetime) -> bool:
    """Return whether ``created_at`` falls within the recency window.

    Args:
        created_at: The most-similar job's creation timestamp.
        now: The reference "now" timestamp.

    Returns:
        ``True`` if the job was created within :data:`RECENCY_WINDOW`.
    """
    if created_at is None:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at >= now - RECENCY_WINDOW


def detect_duplicate(
    new_title: str | None,
    new_description: str | None,
    existing: list[ExistingJob],
    *,
    now: datetime | None = None,
) -> DuplicateAssessment:
    """Classify a candidate job against existing jobs with time-decay rules.

    Args:
        new_title: Candidate job title.
        new_description: Candidate job description.
        existing: Existing jobs to compare against (title, description, date).
        now: Optional reference timestamp (defaults to current UTC time).

    Returns:
        A :class:`DuplicateAssessment` carrying the duplicate flag and a
        0–100 ``duplicate_chance``.
    """
    now = now or datetime.now(timezone.utc)

    candidate = comparison_string(new_title, new_description)
    corpus = [
        (comparison_string(job.job_title, job.job_description), job.created_at)
        for job in existing
    ]
    corpus = [(text, created_at) for text, created_at in corpus if text]

    if not candidate or not corpus:
        return DuplicateAssessment(is_duplicate=False, duplicate_chance=0)

    match = best_match(candidate, [text for text, _ in corpus])
    if match is None or match.score <= SIMILARITY_THRESHOLD:
        return DuplicateAssessment(is_duplicate=False, duplicate_chance=0)

    best_created_at = corpus[match.index][1]
    chance = round(match.score * 100)
    if _is_recent(best_created_at, now):
        return DuplicateAssessment(
            is_duplicate=True,
            duplicate_chance=max(DUPLICATE_CHANCE_FLOOR, chance),
        )
    return DuplicateAssessment(is_duplicate=False, duplicate_chance=chance)
