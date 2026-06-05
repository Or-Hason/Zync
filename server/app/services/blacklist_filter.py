"""Blacklist keyword scanning for the filtration step.

Scope rule: scan ONLY ``job_title + " " + job_description``. The
``company_description`` is deliberately excluded to avoid false positives from
company names and boilerplate marketing text.
"""

from __future__ import annotations


def find_blacklist_hit(
    job_title: str | None,
    job_description: str | None,
    keywords: list[str],
) -> str | None:
    """Return the first blacklist keyword found in the title/description.

    Matching is case-insensitive substring. ``company_description`` is never
    passed in and therefore never scanned.

    Args:
        job_title: Extracted job title.
        job_description: Extracted job description.
        keywords: Blacklist keywords to scan for.

    Returns:
        The original (non-lowercased) keyword on the first match, or ``None``
        when no keyword matches.
    """
    haystack = f"{job_title or ''} {job_description or ''}".lower()
    for keyword in keywords:
        needle = keyword.strip().lower()
        if needle and needle in haystack:
            return keyword
    return None
