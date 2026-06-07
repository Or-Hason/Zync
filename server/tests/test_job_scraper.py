"""Tests for smart HTML content targeting and size enforcement."""

from __future__ import annotations

import pytest

from app.services.job_scraper import (
    MAX_CONTENT_BYTES,
    ContentTooLargeError,
    extract_content,
)

_SIDEBAR_HTML = """
<html><body>
  <header>Site Header Nav</header>
  <nav>Home Jobs Companies</nav>
  <aside class="sidebar related-jobs">
    <h3>Frontend Developer at OtherCo</h3>
    <h3>QA Engineer at ThirdCo</h3>
  </aside>
  <main>
    <h1>Senior Python Engineer</h1>
    <p>Build async FastAPI services backed by PostgreSQL.</p>
  </main>
  <footer>Copyright Footer</footer>
</body></html>
"""

_FALLBACK_HTML = """
<html><body>
  <header>Header text</header>
  <nav>Nav links</nav>
  <div class="menu">Menu items</div>
  <div class="recommended">Recommended Job at OtherCo</div>
  <div class="content">
    <h1>Backend Engineer</h1>
    <p>Design distributed systems in Python.</p>
  </div>
  <footer>Footer text</footer>
</body></html>
"""


class TestSmartTargeting:
    """`<main>`/`<article>` are preferred; chrome is excluded."""

    def test_main_is_targeted_and_sidebar_excluded(self) -> None:
        text = extract_content(_SIDEBAR_HTML)
        assert "Senior Python Engineer" in text
        assert "FastAPI services" in text
        # Sidebar / chrome listings must not bleed into the extracted content.
        assert "Frontend Developer" not in text
        assert "QA Engineer" not in text
        assert "Site Header Nav" not in text
        assert "Copyright Footer" not in text

    def test_article_is_targeted_when_no_main(self) -> None:
        html = (
            "<html><body><nav>menu</nav>"
            "<article><h1>Data Scientist</h1><p>Train ML models.</p></article>"
            "<aside class='sidebar'>Other Role at OtherCo</aside>"
            "</body></html>"
        )
        text = extract_content(html)
        assert "Data Scientist" in text
        assert "Train ML models" in text
        assert "Other Role" not in text


class TestFallbackExtraction:
    """When no `<main>`/`<article>` exists, body is cleaned of chrome."""

    def test_fallback_strips_chrome_and_sidebar_classes(self) -> None:
        text = extract_content(_FALLBACK_HTML)
        assert "Backend Engineer" in text
        assert "distributed systems" in text
        # nav/header/footer tags and sidebar-class elements are removed.
        assert "Header text" not in text
        assert "Nav links" not in text
        assert "Footer text" not in text
        assert "Menu items" not in text
        assert "Recommended Job" not in text

    def test_whitespace_is_normalised(self) -> None:
        html = "<main>  Role   Title \n\n  spaced   out </main>"
        text = extract_content(html)
        assert text == "Role Title spaced out"


class TestSizeEnforcement:
    """Extracted content above the cap is rejected."""

    def test_oversized_content_raises(self) -> None:
        oversized = "word " * ((MAX_CONTENT_BYTES // 5) + 10)
        html = f"<main>{oversized}</main>"
        with pytest.raises(ContentTooLargeError):
            extract_content(html)

    def test_content_at_limit_is_accepted(self) -> None:
        html = "<main>Compact role description.</main>"
        # Well under the cap — must not raise.
        assert "Compact role description." in extract_content(html)
