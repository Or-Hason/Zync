"""Fetch and smart-extract job-post content from a URL.

Job portals wrap a single posting in navigation, headers, footers, and sidebars
listing *other* postings. Letting that chrome bleed into the parsed fields
pollutes the extracted title/description, so we target the semantic
``<main>``/``<article>`` container first and only fall back to a cleaned
``<body>`` when no such container exists. Extracted content is capped so a
runaway page can never overload the downstream AI call.
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Maximum size (UTF-8 bytes) of extracted text. Larger payloads are rejected.
MAX_CONTENT_BYTES = 500 * 1024

# Tags stripped wholesale during fallback body extraction.
_NOISE_TAGS = ("script", "style", "nav", "header", "footer")
# Case-insensitive class substrings that mark a container as chrome/noise.
_NOISE_CLASS_HINTS = ("sidebar", "nav", "menu", "related", "recommended")

_FETCH_TIMEOUT_SECONDS = 30.0
_USER_AGENT = (
    "Mozilla/5.0 (compatible; ZyncBot/1.0; +https://github.com/Or-Hason/Zync)"
)


class JobFetchError(Exception):
    """Raised when a job URL cannot be fetched (network or HTTP-status error)."""


class ContentTooLargeError(Exception):
    """Raised when extracted/raw content exceeds :data:`MAX_CONTENT_BYTES`."""


async def fetch_html(url: str) -> str:
    """Fetch raw HTML for a job URL.

    Args:
        url: Absolute job-post URL.

    Returns:
        The response body as text.

    Raises:
        JobFetchError: On any transport or non-2xx HTTP error.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        logger.warning("Job URL fetch failed", extra={"error": str(exc)})
        raise JobFetchError(str(exc)) from exc


def enforce_content_size(text: str) -> None:
    """Reject content larger than the cap.

    Args:
        text: Extracted or raw job text.

    Raises:
        ContentTooLargeError: If ``text`` exceeds :data:`MAX_CONTENT_BYTES`.
    """
    if len(text.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise ContentTooLargeError(
            f"Content exceeds the {MAX_CONTENT_BYTES // 1024} KB limit."
        )


def extract_content(html: str) -> str:
    """Extract job text from HTML with smart content targeting.

    Primary: text from the first ``<main>`` or ``<article>`` container — this
    keeps sidebar listings of other jobs out of the result. Fallback: the full
    ``<body>`` with scripts, navigation, header, footer, and sidebar-class
    elements removed.

    Args:
        html: Raw page HTML.

    Returns:
        Whitespace-normalised extracted text.

    Raises:
        ContentTooLargeError: If the extracted text exceeds the size cap.
    """
    soup = BeautifulSoup(html, "html.parser")

    container = soup.find("main") or soup.find("article")
    if isinstance(container, Tag):
        text = _clean_text(container.get_text(separator=" "))
    else:
        text = _extract_from_body(soup)

    enforce_content_size(text)
    return text


def _extract_from_body(soup: BeautifulSoup) -> str:
    """Extract cleaned text from the document body (fallback path).

    Args:
        soup: Parsed document.

    Returns:
        Whitespace-normalised body text with chrome elements removed.
    """
    body = soup.body or soup

    for tag in body.find_all(_NOISE_TAGS):
        tag.decompose()

    for element in body.find_all(class_=True):
        if element.decomposed:
            continue
        classes = " ".join(element.get("class") or []).lower()
        if any(hint in classes for hint in _NOISE_CLASS_HINTS):
            element.decompose()

    return _clean_text(body.get_text(separator=" "))


def _clean_text(text: str) -> str:
    """Collapse all runs of whitespace into single spaces.

    Args:
        text: Raw extracted text.

    Returns:
        The text with normalised whitespace and no leading/trailing spaces.
    """
    return " ".join(text.split())
