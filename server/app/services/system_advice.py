"""Rule-based `system_advice` generation for a scored job.

The advice is deterministic — never a second AI call. ``is_duplicate`` and
``duplicate_chance`` encode the 6-month recency decision from duplicate
detection: ``is_duplicate = true`` means a recent (<6 month) near-identical
job, while ``is_duplicate = false`` with a positive ``duplicate_chance`` means
a similar job older than 6 months.

``matched_job_status`` (when available) drives duplicate advice phrasing so the
message reflects whether the user has already acted on the matching job.
"""

from __future__ import annotations

# Score thresholds shared with the low-score auto-reject rule.
LOW_SCORE_THRESHOLD = 40
STRONG_SCORE_THRESHOLD = 70

# Statuses that indicate the user actively applied or is in the pipeline.
_APPLIED_STATUSES = frozenset(
    {
        "applied",
        "assessment_task",
        "assessment_rejected",
        "home_test",
        "home_test_rejected",
        "professional_interview",
        "professional_interview_rejected",
        "hr_interview",
        "hr_interview_rejected",
        "accepted",
    }
)

ADVICE_LOW_SCORE = "Not recommended — this role is a poor match for your profile."

# Recent duplicate (<6 months) — phrasing varies by matched-job status.
ADVICE_RECENT_DUP_APPLIED = (
    "You already applied to this job recently — this appears to be a duplicate."
)
ADVICE_RECENT_DUP_REJECTED = (
    "This job was previously rejected — this appears to be a duplicate."
)
ADVICE_RECENT_DUP_NOT_APPLIED = (
    "This job is already in your list — this appears to be a duplicate."
)
ADVICE_RECENT_DUP_FALLBACK = (
    "This appears to be a duplicate of a recently added job."
)

# Old similar job (>6 months) — phrasing varies by matched-job status.
ADVICE_OLD_SIMILAR_APPLIED = (
    "You applied to a similar role over 6 months ago — worth trying again!"
)
ADVICE_OLD_SIMILAR_REJECTED = (
    "A similar role was previously rejected. Has the job or your profile changed?"
)
ADVICE_OLD_SIMILAR_NOT_APPLIED = (
    "A similar job already exists in your archive from over 6 months ago."
)
ADVICE_OLD_SIMILAR_FALLBACK = "A similar job already exists in your history."

ADVICE_STRONG = "Strong match — recommended to apply."
ADVICE_MODERATE = "Moderate match — consider applying if the role interests you."
ADVICE_UNSCORED = "Could not score this role automatically — review it manually."


def _recent_dup_advice(matched_status: str | None) -> str:
    """Return the appropriate phrasing for a recent duplicate."""
    if matched_status in _APPLIED_STATUSES:
        return ADVICE_RECENT_DUP_APPLIED
    if matched_status == "auto_rejected":
        return ADVICE_RECENT_DUP_REJECTED
    if matched_status == "not_applied":
        return ADVICE_RECENT_DUP_NOT_APPLIED
    return ADVICE_RECENT_DUP_FALLBACK


def _old_similar_advice(matched_status: str | None) -> str:
    """Return the appropriate phrasing for an old similar job."""
    if matched_status in _APPLIED_STATUSES:
        return ADVICE_OLD_SIMILAR_APPLIED
    if matched_status == "auto_rejected":
        return ADVICE_OLD_SIMILAR_REJECTED
    if matched_status == "not_applied":
        return ADVICE_OLD_SIMILAR_NOT_APPLIED
    return ADVICE_OLD_SIMILAR_FALLBACK


def build_system_advice(
    *,
    match_score: int | None,
    is_duplicate: bool,
    duplicate_chance: int | None,
    matched_job_status: str | None = None,
) -> str:
    """Generate the ``system_advice`` string from the ordered rule set.

    Args:
        match_score: The 0–100 match score, or ``None`` when unscored.
        is_duplicate: Whether the job is a recent duplicate.
        duplicate_chance: 0–100 duplicate probability.
        matched_job_status: Status of the best-matching existing job, if any.

    Returns:
        The advice string for the highest-priority matching rule.
    """
    if match_score is not None and match_score < LOW_SCORE_THRESHOLD:
        return ADVICE_LOW_SCORE
    if is_duplicate:
        return _recent_dup_advice(matched_job_status)
    if (duplicate_chance or 0) > 0:
        return _old_similar_advice(matched_job_status)
    if match_score is not None and match_score >= STRONG_SCORE_THRESHOLD:
        return ADVICE_STRONG
    if match_score is not None and LOW_SCORE_THRESHOLD <= match_score < STRONG_SCORE_THRESHOLD:
        return ADVICE_MODERATE
    return ADVICE_UNSCORED
