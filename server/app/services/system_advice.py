"""Rule-based `system_advice` generation for a scored job.

The advice is a deterministic, rule-based recommendation — never a second AI
call. ``is_duplicate`` and ``duplicate_chance`` already encode the 6-month
recency decision from BE-03 duplicate detection: ``is_duplicate = true`` means a
recent (<6 month) near-identical job, while ``is_duplicate = false`` with a
positive ``duplicate_chance`` means a similar job older than 6 months.
"""

from __future__ import annotations

# Score thresholds shared with the low-score auto-reject rule.
LOW_SCORE_THRESHOLD = 40
STRONG_SCORE_THRESHOLD = 70

ADVICE_LOW_SCORE = "Not recommended — this role is a poor match for your profile."
ADVICE_RECENT_DUPLICATE = (
    "You applied to a near-identical job recently — this is likely a duplicate."
)
ADVICE_OLD_SIMILAR = (
    "You applied to a similar job over 6 months ago — worth trying again!"
)
ADVICE_STRONG = "Strong match — recommended to apply."
ADVICE_MODERATE = "Moderate match — consider applying if the role interests you."
# Fallback so the field is always present even when scoring was unavailable.
ADVICE_UNSCORED = "Could not score this role automatically — review it manually."


def build_system_advice(
    *,
    match_score: int | None,
    is_duplicate: bool,
    duplicate_chance: int | None,
) -> str:
    """Generate the `system_advice` string from the ordered rule set.

    Args:
        match_score: The 0–100 match score, or ``None`` when unscored.
        is_duplicate: Whether the job is a recent duplicate.
        duplicate_chance: 0–100 duplicate probability.

    Returns:
        The advice string for the highest-priority matching rule.
    """
    if match_score is not None and match_score < LOW_SCORE_THRESHOLD:
        return ADVICE_LOW_SCORE
    if is_duplicate:
        return ADVICE_RECENT_DUPLICATE
    if not is_duplicate and (duplicate_chance or 0) > 0:
        return ADVICE_OLD_SIMILAR
    if match_score is not None and match_score >= STRONG_SCORE_THRESHOLD:
        return ADVICE_STRONG
    if (
        match_score is not None
        and LOW_SCORE_THRESHOLD <= match_score < STRONG_SCORE_THRESHOLD
    ):
        return ADVICE_MODERATE
    return ADVICE_UNSCORED
