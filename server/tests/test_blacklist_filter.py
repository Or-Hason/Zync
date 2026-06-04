"""Tests for blacklist keyword scanning (title + description only)."""

from __future__ import annotations

from app.services.blacklist_filter import find_blacklist_hit


class TestFindBlacklistHit:
    """Case-insensitive substring scan over title + description."""

    def test_matches_keyword_in_title(self) -> None:
        hit = find_blacklist_hit("Senior PHP Developer", "Build web apps", ["php"])
        assert hit == "php"

    def test_matches_keyword_in_description(self) -> None:
        hit = find_blacklist_hit("Engineer", "Must know WordPress well", ["wordpress"])
        assert hit == "wordpress"

    def test_returns_original_keyword_casing(self) -> None:
        # The returned value preserves the stored keyword's casing.
        hit = find_blacklist_hit("PHP role", None, ["PHP"])
        assert hit == "PHP"

    def test_no_match_returns_none(self) -> None:
        assert find_blacklist_hit("Python Engineer", "FastAPI APIs", ["php"]) is None

    def test_empty_keywords_returns_none(self) -> None:
        assert find_blacklist_hit("Anything", "here", []) is None

    def test_first_match_wins(self) -> None:
        hit = find_blacklist_hit("PHP and Drupal", None, ["drupal", "php"])
        assert hit == "drupal"

    def test_blank_keyword_is_skipped(self) -> None:
        assert find_blacklist_hit("Python role", "desc", ["   ", "python"]) == "python"


class TestCompanyDescriptionNeverScanned:
    """`company_description` is structurally excluded from the scan surface."""

    def test_company_description_is_not_an_argument(self) -> None:
        # The function only accepts title + description; a keyword that would
        # only appear in company_description can never produce a hit.
        hit = find_blacklist_hit(
            "Backend Engineer",
            "Work on our platform",
            ["acme"],  # imagine "Acme" only appears in company_description
        )
        assert hit is None
