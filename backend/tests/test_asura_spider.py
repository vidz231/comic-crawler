"""Tests for the AsuraSpider — parsing logic with mocked HTML responses."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import ParseError
from comic_crawler.spiders.asura import (
    AsuraSpider,
    parse_asura_date,
    parse_chapter_number,
    _abs_url,
)


# ---------------------------------------------------------------------------
# Mock HTML fixtures
# ---------------------------------------------------------------------------

SERIES_PAGE_HTML = """
<html>
<head><title>My Awesome Manhwa - Asura Scans</title></head>
<body>
  <div class="series-info">
    <h3 class="hover:text-themecolor cursor-pointer text-white text-sm">Asura Scans</h3>
    <h3 class="hover:text-themecolor cursor-pointer text-white text-sm shrink-0">My Awesome Manhwa</h3>
    <span class="ml-1 text-xs">9.2</span>
    <span class="text-xl font-bold">My Awesome Manhwa</span>
    <span class="status bg-blue-700">Ongoing</span>
    <p>Followed by 12345 people</p>
    <img src="https://gg.asuracomic.net/storage/media/123/cover-optimized.webp" alt="cover">
    <h3 class="text-[#D9D9D9] font-medium text-sm">Genres</h3>
    <a href="/series?page=1&genres=1">Action,</a>
    <a href="/series?page=1&genres=16">Fantasy,</a>
    <a href="/series?page=1&genres=28">Magic</a>
    <h3 class="text-[#D9D9D9] font-medium text-sm py-0.5">Synopsis My Awesome Manhwa</h3>
    <span class="">There stood a seemingly ordinary shepherd from a distant hill.</span>
    <span class="">Having lived while hiding his talent as a great archwizard, he finally steps out into the world.</span>
    <span class="text-[#A2A2A2] font-normal">read My Awesome Manhwa, My Awesome Manhwa english, download My Awesome Manhwa eng</span>
    <h3 class="text-[#D9D9D9] font-medium text-sm">Author</h3>
    <h3 class="text-[#A2A2A2] text-sm">Test Author</h3>
    <h3 class="text-[#D9D9D9] font-medium text-sm">Artist</h3>
    <h3 class="text-[#A2A2A2] text-sm">Test Artist</h3>
    <h3 class="text-sm text-[#A2A2A2]">Status</h3>
    <h3 class="text-sm text-[#A2A2A2] capitalize">Ongoing</h3>
    <h3 class="text-sm text-[#A2A2A2]">Type</h3>
    <h3 class="text-sm text-white hover:text-themecolor capitalize cursor-pointer">Manhwa</h3>
  </div>
  <div class="chapter-list">
    <a href="/my-awesome-manhwa-abc123/chapter/0"><h3 class="text-sm text-white font-medium">Chapter 0</h3><h3 class="text-xs text-[#A2A2A2]">January 31st 2026</h3></a>
    <a href="/my-awesome-manhwa-abc123/chapter/1"><h3 class="text-sm text-white font-medium">Chapter 1</h3><h3 class="text-xs text-[#A2A2A2]">January 31st 2026</h3></a>
    <a href="/my-awesome-manhwa-abc123/chapter/2"><h3 class="text-sm text-white font-medium">Chapter 2</h3><h3 class="text-xs text-[#A2A2A2]">February 1st 2026</h3></a>
    <a href="/my-awesome-manhwa-abc123/chapter/10"><h3 class="text-sm text-white font-medium">Chapter 10</h3><h3 class="text-xs text-[#A2A2A2]">February 3rd 2026</h3></a>
    <a href="/my-awesome-manhwa-abc123/chapter/24"><h3 class="text-sm text-white font-medium">Chapter 24</h3><h3 class="text-xs text-[#A2A2A2]">February 24th 2026</h3></a>
    <!-- Duplicate link that should be deduped -->
    <a href="/my-awesome-manhwa-abc123/chapter/24"><h3 class="text-sm text-white font-medium">Chapter 24</h3><h3 class="text-xs text-[#A2A2A2]">February 24th 2026</h3></a>
  </div>
</body>
</html>
"""

CHAPTER_PAGE_HTML = """
<html>
<head><title>My Awesome Manhwa Chapter 1 - Asura Scans</title></head>
<body>
  <div class="reader">
    <img src="https://gg.asuracomic.net/storage/media/500/page-001.webp" alt="page 1">
    <img src="https://gg.asuracomic.net/storage/media/500/page-002.webp" alt="page 2">
    <img src="https://gg.asuracomic.net/storage/media/500/page-003.webp" alt="page 3">
    <!-- UI images that should be filtered out -->
    <img src="https://example.com/ads/banner.jpg" alt="ad">
    <img src="https://gg.asuracomic.net/storage/media/500/thumb-small.webp" alt="thumb">
    <img src="https://gg.asuracomic.net/storage/icons/logo.png" alt="logo">
    <!-- Duplicate that should be skipped -->
    <img src="https://gg.asuracomic.net/storage/media/500/page-001.webp" alt="duplicate">
  </div>
  <div class="nav">
    <a href="/series/my-awesome-manhwa-abc123/chapter/0">Prev</a>
    <a href="/series/my-awesome-manhwa-abc123/chapter/2">Next</a>
  </div>
</body>
</html>
"""

SEARCH_PAGE_HTML = """
<html>
<head><title>Series - Asura Scans</title></head>
<body>
  <div class="series-list">
    <a href="/series/manga-one-aaa111">Manga One</a>
    <a href="/series/manga-two-bbb222">Manga Two</a>
    <a href="/series/manga-three-ccc333">Manga Three</a>
    <!-- chapter link should be ignored -->
    <a href="/series/manga-one-aaa111/chapter/5">Chapter 5</a>
    <!-- pagination link should be ignored -->
    <a href="/series?page=2">Next</a>
    <!-- duplicate slug should be deduped -->
    <a href="/series/manga-one-aaa111">Manga One Again</a>
  </div>
</body>
</html>
"""

SEARCH_CARDS_HTML = """
<html>
<head><title>Series - Asura Scans</title></head>
<body>
  <div class="series-list">
    <a href="/series/solo-farming-in-the-tower-3a65927e">
      <div class="w-full block">
        <div>
          <div class="flex h-[250px] overflow-hidden relative">
            <span class="status bg-blue-700">Ongoing</span>
            <img alt="" loading="lazy" src="https://gg.asuracomic.net/storage/media/414119/conversions/cover-thumb-small.webp" class="rounded-md">
            <div class="absolute bottom-[0px] flex justify-center left-[5px] mb-[5px] rounded-[3px] text-white bg-[#a12e24]">
              <span class="text-[10px] font-bold py-[2px] px-[7px]">MANHWA</span>
            </div>
          </div>
          <div class="block w-[100%] h-auto items-center">
            <span class="block text-[13.3px] font-bold">Solo Farming In The Tower</span>
            <span class="text-[13px] text-[#999]">Chapter 115</span>
            <span class="flex text-[12px] text-[#999]">
              <div class="flex justify-between">
                <div class="flex items-center gap-0.5">
                  <span class="ml-1 text-xs">9.6</span>
                </div>
              </div>
            </span>
          </div>
        </div>
      </div>
    </a>
    <a href="/series/solo-leveling-d0aa86d9">
      <div class="w-full block">
        <div>
          <div class="flex h-[250px] overflow-hidden relative">
            <span class="status bg-green-700">Completed</span>
            <img alt="" loading="lazy" src="https://gg.asuracomic.net/storage/media/256/conversions/cover-thumb-small.webp" class="rounded-md">
            <div class="absolute bottom-[0px]">
              <span class="text-[10px] font-bold py-[2px] px-[7px]">MANHWA</span>
            </div>
          </div>
          <div class="block w-[100%] h-auto items-center">
            <span class="block text-[13.3px] font-bold">Solo Leveling</span>
            <span class="text-[13px] text-[#999]">Chapter 200</span>
            <span class="flex text-[12px] text-[#999]">
              <div class="flex justify-between">
                <div class="flex items-center gap-0.5">
                  <span class="ml-1 text-xs">9.7</span>
                </div>
              </div>
            </span>
          </div>
        </div>
      </div>
    </a>
  </div>
</body>
</html>
"""

EMPTY_SEARCH_HTML = """
<html>
<head><title>Series - Asura Scans</title></head>
<body>
  <div class="series-list">
    <a href="/series?page=1">Previous</a>
    <a href="/series?page=1">Next</a>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper to build a mock Scrapling response from HTML
# ---------------------------------------------------------------------------


def _mock_response(html: str) -> MagicMock:
    """Create a mock Scrapling Adaptor response from an HTML string.

    Uses a real HTML parser to support CSS selectors properly.
    """
    from scrapling.parser import Adaptor

    return Adaptor(html, auto_match=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spider(tmp_path: Path) -> AsuraSpider:
    """AsuraSpider with a temp output dir and fetch mocked out."""
    config = CrawlerConfig(output_dir=tmp_path / "output", log_level="DEBUG")
    return AsuraSpider(config=config)


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------


class TestParseChapterNumber:
    """Test chapter number extraction from URLs."""

    def test_integer_chapter(self) -> None:
        assert parse_chapter_number("/series/slug/chapter/10") == 10.0

    def test_zero_chapter(self) -> None:
        assert parse_chapter_number("/series/slug/chapter/0") == 0.0

    def test_decimal_chapter(self) -> None:
        assert parse_chapter_number("/series/slug/chapter/10.5") == 10.5

    def test_full_url(self) -> None:
        url = "https://asuracomic.net/series/my-manga-abc123/chapter/24"
        assert parse_chapter_number(url) == 24.0

    def test_trailing_slash(self) -> None:
        assert parse_chapter_number("/series/slug/chapter/5/") == 5.0

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_chapter_number("/series/slug/no-chapter-here")


class TestParseAsuraDate:
    """Test Asura date string parsing."""

    def test_standard_date(self) -> None:
        result = parse_asura_date("January 31st 2026")
        assert result == datetime(2026, 1, 31)

    def test_second_ordinal(self) -> None:
        result = parse_asura_date("February 2nd 2026")
        assert result == datetime(2026, 2, 2)

    def test_third_ordinal(self) -> None:
        result = parse_asura_date("March 3rd 2026")
        assert result == datetime(2026, 3, 3)

    def test_th_ordinal(self) -> None:
        result = parse_asura_date("February 24th 2026")
        assert result == datetime(2026, 2, 24)

    def test_empty_string_returns_none(self) -> None:
        assert parse_asura_date("") is None

    def test_invalid_date_returns_none(self) -> None:
        assert parse_asura_date("not a date") is None


class TestAbsUrl:
    """Test URL resolution helper."""

    def test_absolute_url_unchanged(self) -> None:
        url = "https://example.com/path"
        assert _abs_url(url) == url

    def test_relative_resolved(self) -> None:
        assert _abs_url("/series/test").startswith("https://asuracomic.net")


# ---------------------------------------------------------------------------
# Tests: Series parsing
# ---------------------------------------------------------------------------


class TestParseSeries:
    """Test series metadata + chapter list extraction."""

    def test_extracts_title(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        assert result["series"]["title"] == "My Awesome Manhwa"

    def test_extracts_cover_url(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        assert "gg.asuracomic.net" in result["series"]["cover_url"]

    def test_extracts_synopsis(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        assert result["series"]["synopsis"] is not None
        assert "shepherd" in result["series"]["synopsis"].lower()

    def test_extracts_chapters(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        chapters = result["chapters"]
        # Should have 5 unique chapters (0, 1, 2, 10, 24) — duplicate chapter 24 is deduped
        assert len(chapters) == 5

    def test_chapters_sorted_by_number(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        numbers = [c["number"] for c in result["chapters"]]
        assert numbers == sorted(numbers)
        assert numbers == [0.0, 1.0, 2.0, 10.0, 24.0]

    def test_chapter_has_date(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        # Chapter 24 should have February 24th 2026
        ch24 = [c for c in result["chapters"] if c["number"] == 24.0][0]
        assert ch24["date_published"] is not None

    def test_chapter_url_is_absolute(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://asuracomic.net/series/test-slug")

        for ch in result["chapters"]:
            assert ch["url"].startswith("https://")


# ---------------------------------------------------------------------------
# Tests: Chapter image extraction
# ---------------------------------------------------------------------------


class TestParseChapter:
    """Test chapter page image URL extraction."""

    def test_extracts_page_images(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.parse_chapter(
                "https://asuracomic.net/series/test/chapter/1",
                "My Awesome Manhwa",
            )

        # Should extract 3 CDN images, filtering out: ad, thumb, logo, duplicate
        assert len(pages) == 3

    def test_pages_numbered_sequentially(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.parse_chapter(
                "https://asuracomic.net/series/test/chapter/1",
                "My Awesome Manhwa",
            )

        page_numbers = [p["page_number"] for p in pages]
        assert page_numbers == [1, 2, 3]

    def test_pages_have_cdn_urls(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.parse_chapter(
                "https://asuracomic.net/series/test/chapter/1",
                "My Awesome Manhwa",
            )

        for page in pages:
            assert "gg.asuracomic.net" in page["image_url"]

    def test_pages_have_correct_metadata(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.parse_chapter(
                "https://asuracomic.net/series/test/chapter/1",
                "My Awesome Manhwa",
            )

        for page in pages:
            assert page["series_title"] == "My Awesome Manhwa"
            assert page["chapter_number"] == 1.0
            assert page["local_path"] is None

    def test_filters_non_cdn_images(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.parse_chapter(
                "https://asuracomic.net/series/test/chapter/1",
                "Test",
            )

        urls = [p["image_url"] for p in pages]
        assert not any("example.com" in u for u in urls)

    def test_filters_thumbnails(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_do_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.parse_chapter(
                "https://asuracomic.net/series/test/chapter/1",
                "Test",
            )

        urls = [p["image_url"] for p in pages]
        assert not any("thumb" in u for u in urls)


# ---------------------------------------------------------------------------
# Tests: Search / browse parsing
# ---------------------------------------------------------------------------


class TestExtractSeriesLinks:
    """Test series link discovery from search pages."""

    def test_extracts_unique_series(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        links = spider._extract_series_links(response)

        # Should find 3 unique series (deduping "manga-one-aaa111")
        assert len(links) == 3

    def test_ignores_chapter_links(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        links = spider._extract_series_links(response)

        urls = [l["url"] for l in links]
        assert not any("/chapter/" in u for u in urls)

    def test_returns_absolute_urls(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        links = spider._extract_series_links(response)

        for link in links:
            assert link["url"].startswith("https://")

    def test_empty_search_returns_empty(self, spider: AsuraSpider) -> None:
        response = _mock_response(EMPTY_SEARCH_HTML)
        links = spider._extract_series_links(response)

        assert len(links) == 0


class TestExtractSeriesCards:
    """Test rich card extraction from listing page — title must not be 'MANHWA'."""

    def test_extracts_correct_titles(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        assert len(cards) == 2
        assert cards[0]["title"] == "Solo Farming In The Tower"
        assert cards[1]["title"] == "Solo Leveling"

    def test_title_is_not_type_label(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        for card in cards:
            assert card["title"].upper() != "MANHWA"

    def test_extracts_slug(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        assert cards[0]["slug"] == "solo-farming-in-the-tower-3a65927e"
        assert cards[1]["slug"] == "solo-leveling-d0aa86d9"

    def test_extracts_cover_url(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        for card in cards:
            assert card["cover_url"] is not None
            assert "gg.asuracomic.net" in card["cover_url"]

    def test_extracts_status(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        assert cards[0]["status"] == "Ongoing"
        assert cards[1]["status"] == "Completed"

    def test_extracts_latest_chapter(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        assert cards[0]["latest_chapter"] == 115.0
        assert cards[1]["latest_chapter"] == 200.0

    def test_extracts_rating(self, spider: AsuraSpider) -> None:
        response = _mock_response(SEARCH_CARDS_HTML)
        cards = spider._extract_series_cards(response)

        assert cards[0]["rating"] == 9.6
        assert cards[1]["rating"] == 9.7

class TestCrawlSearchPagination:
    """Test search pagination logic."""

    def test_stops_on_empty_results(self, spider: AsuraSpider) -> None:
        """When a page has no series links, pagination should stop."""
        call_count = 0

        def mock_fetch_listing(url: str) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_response(SEARCH_PAGE_HTML)
            return _mock_response(EMPTY_SEARCH_HTML)

        with patch.object(spider, "_fetch_listing", side_effect=mock_fetch_listing):
            results = spider.crawl_search(max_pages=5)

        # Should stop after 2 fetches (page 1 has results, page 2 is empty)
        assert call_count == 2
        assert len(results) == 3

    def test_respects_max_pages(self, spider: AsuraSpider) -> None:
        with patch.object(spider, "_fetch_listing", return_value=_mock_response(SEARCH_PAGE_HTML)):
            results = spider.crawl_search(max_pages=1)

        # Only crawl 1 page
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Tests: Orchestration (run_single)
# ---------------------------------------------------------------------------


class TestRunSingle:
    """Test the single-series orchestration flow."""

    def test_run_single_exports_json(self, spider: AsuraSpider, tmp_path: Path) -> None:
        """run_single should produce a JSON file with series, chapters, pages."""

        def mock_do_fetch(url: str, *, network_idle: bool, wait_selector: Any, block_images: bool) -> Any:
            if "/chapter/" in url:
                return _mock_response(CHAPTER_PAGE_HTML)
            return _mock_response(SERIES_PAGE_HTML)

        with patch.object(spider, "_do_fetch", side_effect=mock_do_fetch):
            result = spider.run_single("https://asuracomic.net/series/test-slug")

        # Verify result structure
        assert "series" in result
        assert "chapters" in result
        assert "pages" in result
        assert result["series"]["title"] == "My Awesome Manhwa"
        assert len(result["chapters"]) == 5
        assert len(result["pages"]) > 0

        # Verify JSON file was created
        output_dir = spider._config.output_dir
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_run_single_handles_chapter_errors(
        self, spider: AsuraSpider
    ) -> None:
        """Failing chapters should be logged and skipped, not crash."""
        call_count = 0

        def mock_do_fetch(url: str, *, network_idle: bool, wait_selector: Any, block_images: bool) -> Any:
            nonlocal call_count
            call_count += 1
            if "/chapter/" in url:
                from comic_crawler.exceptions import FetchError
                raise FetchError("Connection failed", url=url)
            return _mock_response(SERIES_PAGE_HTML)

        with patch.object(spider, "_do_fetch", side_effect=mock_do_fetch):
            result = spider.run_single("https://asuracomic.net/series/test-slug")

        # Series + chapters should still be populated, pages empty due to errors
        assert result["series"]["title"] == "My Awesome Manhwa"
        assert len(result["chapters"]) == 5
        assert len(result["pages"]) == 0
