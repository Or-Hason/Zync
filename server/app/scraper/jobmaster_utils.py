"""Utilities and helpers for the JobMaster scraper."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup, Tag


# Source id stamped onto every saved job's search_filters JSONB.
SCRAPER_SOURCE = "jobmaster"

# Substrings that mark an anchor href as an individual job posting.
JOB_LINK_HINTS = ("checknum.asp",)


@dataclass
class ScanReport:
    """Summary of a completed (or aborted) scan, for logging and tests."""

    aborted_reason: str | None = None
    discovered: int = 0
    new_links: int = 0
    processed: int = 0
    first_run: bool = False


def build_search_url(base_url: str, target_role: str) -> str:
    """Build the JobMaster keyword-search URL for a role.

    Args:
        base_url: Site base URL.
        target_role: The role to search for (URL-encoded into the ``q`` param).

    Returns:
        The absolute search URL.
    """
    root = base_url if base_url.endswith("/") else f"{base_url}/"
    return urljoin(root, f"jobs/?q={quote_plus(target_role.strip())}")


def extract_job_links(html: str, base_url: str) -> list[str]:
    """Extract absolute, de-duplicated job-posting links from a results page.
    
    Args:
        html: Raw search-results HTML.
        base_url: Base URL used to resolve relative hrefs to absolute.

    Returns:
        Ordered, de-duplicated absolute job URLs (empty when none match).
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = str(anchor.get("href") or "").strip()
        if not href or not any(hint in href.lower() for hint in JOB_LINK_HINTS):
            continue
        absolute = urljoin(base_url, href)
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links


def select_new_links(scraped: list[str], known_urls: set[str]) -> list[str]:
    """Return scraped links not already present in the DB, order preserved.
    
    Args:
        scraped: Links extracted from the results page.
        known_urls: URLs already stored in ``jobs.source_url``.

    Returns:
        Only the newly discovered links.
    """
    return [url for url in scraped if url not in known_urls]


def apply_scan_caps(
    links: list[str], *, is_first_run: bool, initial_limit: int, max_per_scan: int
) -> list[str]:
    """Apply the first-run and per-scan safety caps to the work list.
    
    On the first run the list is trimmed to the last ``initial_limit`` entries;
    the ``max_per_scan`` ceiling is then applied on every run as a hard guard
    against uncontrolled API usage.

    Args:
        links: Newly discovered links.
        is_first_run: Whether this is the first scan for the source.
        initial_limit: Max jobs to process on the first run.
        max_per_scan: Absolute ceiling for any single scan.

    Returns:
        The capped list of links to process.
    """
    capped = links[-initial_limit:] if is_first_run else links
    return capped[: max(0, max_per_scan)]
