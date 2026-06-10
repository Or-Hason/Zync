"""JobMaster background scraper.

Reads ``target_role`` from the active resume, fetches the JobMaster search page,
extracts individual job links, drops URLs already known to the DB, and pushes the
remaining ones through the shared scoring pipeline (:func:`run_job_pipeline`) —
never via an HTTP self-call.

Cost-safety is layered on purpose, because an uncapped scan would translate
directly into uncontrolled Gemini usage:
  * The scan only runs when the user enabled ``auto_scan_enabled`` AND the
    process-level ``scheduler_enabled`` flag is on.
  * The FIRST scan for this source is capped to ``INITIAL_SCAN_LIMIT`` jobs.
  * EVERY scan (including later ones) is capped to ``MAX_JOBS_PER_SCAN`` jobs.
  * Already-known URLs are skipped, so jobs are never re-fetched or re-scored.
  * If Gemini reports every model rate-limited, the scan aborts immediately
    instead of hammering the API for the rest of the batch.

Defensive parsing (CLAUDE.md): the portal markup is treated as untrusted — a
missing container or zero matching links degrades to an empty result, never a
crash. PII rule: only counts and the search role are logged, never job text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup, Tag
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_pipeline import KIND_GEMINI_UNAVAILABLE, run_job_pipeline
from app.services.job_repository import count_jobs_for_source, load_known_source_urls
from app.services.job_scraper import (
    ContentTooLargeError,
    JobFetchError,
    extract_content,
    fetch_html,
)

logger = logging.getLogger(__name__)

# Source id stamped onto every saved job's search_filters JSONB.
SCRAPER_SOURCE = "jobmaster"

# Substrings that mark an anchor href as an individual job posting. JobMaster
# routes job clicks through a tracking endpoint (``/code/kot/click.asp?i=<id>``);
# this is the single site-specific signal and the one place to adjust if the
# portal changes its link structure. Kept deliberately narrow so navigation and
# category links are never mistaken for jobs (which would waste Gemini calls).
JOB_LINK_HINTS = ("click.asp",)


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
        base_url: Site base URL (e.g. ``https://www.jobmaster.co.il/``).
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


async def _process_link(
    url: str,
    *,
    db: AsyncSession,
    ollama,
    gemini,
    store,
    active_resume,
    search_term: str,
    is_first_run: bool,
) -> str | None:
    """Fetch one job page and run it through the scoring pipeline.

    Args:
        url: Absolute job-posting URL.
        db: Active async DB session.
        ollama: Ollama client.
        gemini: Gemini client.
        store: Settings store.
        active_resume: The active resume (passed through to avoid re-loading).
        search_term: The role searched for (stamped into search_filters).
        is_first_run: Whether this scan is the source's first run.

    Returns:
        The pipeline outcome kind, or ``None`` when the page could not be
        fetched/extracted (job skipped).
    """
    try:
        content = extract_content(await fetch_html(url))
    except (JobFetchError, ContentTooLargeError) as exc:
        logger.warning("Skipping job — fetch/extract failed", extra={"error": str(exc)})
        return None

    search_filters = {
        "source": SCRAPER_SOURCE,
        "search_term": search_term,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "initial_run": is_first_run,
    }
    outcome = await run_job_pipeline(
        db=db,
        ollama=ollama,
        gemini=gemini,
        store=store,
        content=content,
        source_url=url,
        source_type=SCRAPER_SOURCE,
        search_filters=search_filters,
        active_resume=active_resume,
    )
    if outcome.job is not None:
        logger.info(
            "Scraper processed job",
            extra={"job_id": str(outcome.job.id), "source_type": SCRAPER_SOURCE},
        )
    return outcome.kind


async def run_scan(
    *,
    db: AsyncSession,
    ollama,
    gemini,
    store,
    base_url: str,
    initial_limit: int,
    max_per_scan: int,
) -> ScanReport:
    """Run one full JobMaster scan and return a summary report.

    Args:
        db: Active async DB session.
        ollama: Ollama client.
        gemini: Gemini client.
        store: Settings store.
        base_url: JobMaster base URL.
        initial_limit: First-run job cap.
        max_per_scan: Per-scan hard ceiling.

    Returns:
        A :class:`ScanReport` describing what happened.
    """
    # Imported lazily to avoid a scraper→api import at module load time.
    from app.api.resumes_active import load_active_resume

    active_resume = await load_active_resume(db)
    if active_resume is None:
        logger.warning("Scan aborted — no active resume.")
        return ScanReport(aborted_reason="no_active_resume")

    structured = active_resume.structured_data or {}
    target_role = str(structured.get("target_role") or "").strip()
    if not target_role:
        logger.warning("Scan aborted — active resume has no target_role.")
        return ScanReport(aborted_reason="no_target_role")

    search_url = build_search_url(base_url, target_role)
    try:
        html = await fetch_html(search_url)
    except JobFetchError as exc:
        logger.warning("Scan aborted — search fetch failed", extra={"error": str(exc)})
        return ScanReport(aborted_reason="search_fetch_failed")

    discovered = extract_job_links(html, base_url)
    known_urls = await load_known_source_urls(db)
    new_links = select_new_links(discovered, known_urls)

    is_first_run = await count_jobs_for_source(db, SCRAPER_SOURCE) == 0
    to_process = apply_scan_caps(
        new_links,
        is_first_run=is_first_run,
        initial_limit=initial_limit,
        max_per_scan=max_per_scan,
    )

    processed = 0
    for url in to_process:
        kind = await _process_link(
            url,
            db=db,
            ollama=ollama,
            gemini=gemini,
            store=store,
            active_resume=active_resume,
            search_term=target_role,
            is_first_run=is_first_run,
        )
        if kind == KIND_GEMINI_UNAVAILABLE:
            # All models rate-limited — stop now rather than burning the batch.
            logger.warning("Scan stopped early — all Gemini models rate-limited.")
            break
        if kind is not None:
            processed += 1

    logger.info(
        "Scan complete",
        extra={
            "discovered": len(discovered),
            "new_links": len(new_links),
            "processed": processed,
            "first_run": is_first_run,
        },
    )
    return ScanReport(
        discovered=len(discovered),
        new_links=len(new_links),
        processed=processed,
        first_run=is_first_run,
    )
