"""Content-based duplicate detection via TF-IDF cosine similarity.

Comparison runs on each job's normalised *raw ingested text*, not the AI-parsed
title/description: the local model rephrases its parsed output between runs, so
comparing parsed text let near-identical postings slip through. Raw text is
stable for identical input and barely shifts when a couple of incidental lines
are added/removed, so similarity stays high. A new job is compared against
recent existing jobs and classified with time-decay rules: a strong match
against a recent post is a true duplicate, while the same match against an old
post is flagged only as a re-application candidate (not an outright duplicate).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.text_similarity import best_match, comparison_string

# Re-exported under the historical private name so previous tests keep working.
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

    raw_content: str | None
    created_at: datetime
    status: str | None = None


def normalize_content(text: str | None) -> str:
    """Normalise raw ingested text for stable similarity comparison.

    Lowercases and collapses all runs of whitespace to single spaces so that
    incidental line-break / spacing differences do not lower the score.

    Args:
        text: Raw ingested job text (may be ``None``).

    Returns:
        The normalised single-line string (empty when input is blank/None).
    """
    if not text:
        return ""
    return " ".join(text.split()).casefold()


@dataclass(frozen=True)
class DuplicateAssessment:
    """Outcome of duplicate detection for a candidate job."""

    is_duplicate: bool
    duplicate_chance: int
    matched_job_status: str | None = None


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
    new_raw_content: str | None,
    existing: list[ExistingJob],
    *,
    now: datetime | None = None,
) -> DuplicateAssessment:
    """Classify a candidate job against existing jobs with time-decay rules.

    Args:
        new_raw_content: Candidate job's raw ingested text.
        existing: Existing jobs to compare against (raw content, date).
        now: Optional reference timestamp (defaults to current UTC time).

    Returns:
        A :class:`DuplicateAssessment` carrying the duplicate flag and a
        0–100 ``duplicate_chance``.
    """
    now = now or datetime.now(timezone.utc)

    candidate = normalize_content(new_raw_content)
    corpus = [
        (normalize_content(job.raw_content), job.created_at, job.status)
        for job in existing
    ]
    corpus = [(text, created_at, status) for text, created_at, status in corpus if text]

    if not candidate or not corpus:
        return DuplicateAssessment(is_duplicate=False, duplicate_chance=0)

    match = best_match(candidate, [text for text, _, _ in corpus])
    if match is None or match.score <= SIMILARITY_THRESHOLD:
        return DuplicateAssessment(is_duplicate=False, duplicate_chance=0)

    best_created_at, best_status = corpus[match.index][1], corpus[match.index][2]
    chance = round(match.score * 100)
    if _is_recent(best_created_at, now):
        return DuplicateAssessment(
            is_duplicate=True,
            duplicate_chance=max(DUPLICATE_CHANCE_FLOOR, chance),
            matched_job_status=best_status,
        )
    return DuplicateAssessment(
        is_duplicate=False,
        duplicate_chance=chance,
        matched_job_status=best_status,
    )
