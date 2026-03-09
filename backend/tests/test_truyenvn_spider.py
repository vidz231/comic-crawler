"""Tests for the TruyenVNSpider — parsing logic with mocked HTML responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import ParseError
from comic_crawler.spiders.truyenvn import TruyenVNSpider
from comic_crawler.spiders.truyenvn_parser import (
    TruyenVNPageParser,
    abs_url,
    parse_chapter_number_from_slug,
)


# ---------------------------------------------------------------------------
# Mock HTML fixtures (Madara WP theme structure)
# ---------------------------------------------------------------------------

SERIES_PAGE_HTML = """
<html>
<head><title>Đồ Chơi XX - TruyenVN</title></head>
<body>
  <div class="post-title"><h1>Đồ Chơi XX Ở Công Trường Xây Dựng</h1></div>
  <div class="description-summary">
    <div class="summary__content">
      <p>Câu chuyện về một nhóm công nhân xây dựng và cuộc sống hàng ngày của họ tại công trường. Mỗi ngày đều mang đến những tình huống bất ngờ.</p>
    </div>
  </div>
  <div class="summary_image">
    <img src="https://truyenvn.shop/wp-content/uploads/2026/02/truyen-do-choi.jpg" alt="cover">
  </div>
  <div class="post-content">
    <div class="post-content_item mg_status">
      <div class="summary-heading"><h5>Tình trạng</h5></div>
      <div class="summary-content">OnGoing</div>
    </div>
    <div class="post-content_item mg_genres">
      <div class="summary-heading"><h5>Thể loại</h5></div>
      <div class="genres-content">
        <a href="/genre/drama/">Drama,</a>
        <a href="/genre/romance/">Romance,</a>
        <a href="/genre/comedy/">Comedy</a>
      </div>
    </div>
  </div>
  <div class="post-content_item">
    <div class="author-content"><a href="/author/test-author/">Test Author</a></div>
  </div>
  <div class="post-content_item">
    <div class="artist-content"><a href="/artist/test-artist/">Test Artist</a></div>
  </div>
  <div class="post-total-rating"><span class="score">8.5</span></div>

  <div class="listing-chapters_wrap">
    <ul class="main version-chap">
      <li class="wp-manga-chapter">
        <a href="https://truyenvn.shop/truyen-tranh/do-choi-xx/chapter-5/">Chapter 5</a>
        <span class="chapter-release-date"><i>1 ngày trước</i></span>
      </li>
      <li class="wp-manga-chapter">
        <a href="https://truyenvn.shop/truyen-tranh/do-choi-xx/chapter-4/">Chapter 4</a>
        <span class="chapter-release-date"><i>3 ngày trước</i></span>
      </li>
      <li class="wp-manga-chapter">
        <a href="https://truyenvn.shop/truyen-tranh/do-choi-xx/chapter-3/">Chapter 3</a>
        <span class="chapter-release-date"><i>5 ngày trước</i></span>
      </li>
      <li class="wp-manga-chapter">
        <a href="https://truyenvn.shop/truyen-tranh/do-choi-xx/chapter-2/">Chapter 2</a>
        <span class="chapter-release-date"><i>1 tuần trước</i></span>
      </li>
      <li class="wp-manga-chapter">
        <a href="https://truyenvn.shop/truyen-tranh/do-choi-xx/chapter-1/">Chapter 1</a>
        <span class="chapter-release-date"><i>2 tuần trước</i></span>
      </li>
      <!-- Duplicate chapter that should be deduped -->
      <li class="wp-manga-chapter">
        <a href="https://truyenvn.shop/truyen-tranh/do-choi-xx/chapter-1/">Chapter 1</a>
        <span class="chapter-release-date"><i>2 tuần trước</i></span>
      </li>
    </ul>
  </div>
</body>
</html>
"""

CHAPTER_PAGE_HTML = """
<html>
<head><title>Đọc Truyện Đồ Chơi XX Ở Công Trường Xây Dựng Chapter 1 Tiếng Việt - TruyenVN</title></head>
<body>
  <div class="breadcrumb">
    <a href="/">Trang chủ</a>
    <a href="/truyen-tranh/">Truyện Tranh</a>
    <a href="/truyen-tranh/do-choi-xx/">Đồ Chơi XX Ở Công Trường Xây Dựng</a>
    <span>Chapter 1</span>
  </div>
  <div class="reading-content">
    <div class="page-break">
      <img id="image-0" src="https://truyenvn.shop/wp-content/uploads/WP-manga/data/slug/page-001.jpg" alt="page 1">
    </div>
    <div class="page-break">
      <img id="image-1" src="https://truyenvn.shop/wp-content/uploads/WP-manga/data/slug/page-002.jpg" alt="page 2">
    </div>
    <div class="page-break">
      <img id="image-2" src="https://truyenvn.shop/wp-content/uploads/WP-manga/data/slug/page-003.jpg" alt="page 3">
    </div>
    <!-- Duplicate that should be skipped -->
    <div class="page-break">
      <img id="image-dup" src="https://truyenvn.shop/wp-content/uploads/WP-manga/data/slug/page-001.jpg" alt="dup">
    </div>
    <!-- UI image that should be filtered -->
    <div class="page-break">
      <img src="https://truyenvn.shop/wp-content/uploads/logo.png" alt="logo">
    </div>
  </div>
  <div class="nav">
    <a class="prev_page" href="/truyen-tranh/do-choi-xx/chapter-0/">Prev</a>
    <a class="next_page" href="/truyen-tranh/do-choi-xx/chapter-2/">Next</a>
  </div>
</body>
</html>
"""

SEARCH_PAGE_HTML = """
<html>
<head><title>You searched for test | TruyenVN</title></head>
<body>
  <div class="search-wrap">
    <div class="c-tabs-item">
      <div class="c-tabs-item__content">
        <div class="tab-thumb">
          <a href="https://truyenvn.shop/truyen-tranh/manga-one/">
            <img src="https://truyenvn.shop/wp-content/uploads/cover1-193x278.jpg" alt="cover">
          </a>
        </div>
        <div class="tab-summary">
          <div class="post-title"><h3><a href="https://truyenvn.shop/truyen-tranh/manga-one/">Manga One</a></h3></div>
          <div class="meta-item latest-chap">
            <span class="chapter font-meta"><a href="/truyen-tranh/manga-one/chapter-10/">Chapter 10</a></span>
          </div>
          <div class="post-content_item mg_status">
            <div class="summary-content">OnGoing</div>
          </div>
          <div class="post-total-rating"><span class="score">9.0</span></div>
        </div>
      </div>
      <div class="c-tabs-item__content">
        <div class="tab-thumb">
          <a href="https://truyenvn.shop/truyen-tranh/manga-two/">
            <img src="https://truyenvn.shop/wp-content/uploads/cover2-193x278.jpg" alt="cover">
          </a>
        </div>
        <div class="tab-summary">
          <div class="post-title"><h3><a href="https://truyenvn.shop/truyen-tranh/manga-two/">Manga Two</a></h3></div>
          <div class="meta-item latest-chap">
            <span class="chapter font-meta"><a href="/truyen-tranh/manga-two/chapter-25/">Chapter 25</a></span>
          </div>
          <div class="post-content_item mg_status">
            <div class="summary-content">Completed</div>
          </div>
          <div class="post-total-rating"><span class="score">7.5</span></div>
        </div>
      </div>
      <!-- Duplicate that should be deduped -->
      <div class="c-tabs-item__content">
        <div class="tab-thumb">
          <a href="https://truyenvn.shop/truyen-tranh/manga-one/">
            <img src="https://truyenvn.shop/wp-content/uploads/cover1-193x278.jpg" alt="cover">
          </a>
        </div>
        <div class="tab-summary">
          <div class="post-title"><h3><a href="https://truyenvn.shop/truyen-tranh/manga-one/">Manga One Again</a></h3></div>
        </div>
      </div>
    </div>
  </div>
  <div class="nav-previous"><a href="/page/2/?s=test&post_type=wp-manga">Older Posts</a></div>
</body>
</html>
"""

EMPTY_SEARCH_HTML = """
<html>
<head><title>You searched for nothing | TruyenVN</title></head>
<body>
  <div class="search-wrap">
    <div class="c-tabs-item">
    </div>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper to build a mock Scrapling response from HTML
# ---------------------------------------------------------------------------


def _mock_response(html: str) -> MagicMock:
    """Create a mock Scrapling Adaptor response from an HTML string."""
    from scrapling.parser import Adaptor

    return Adaptor(html, auto_match=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spider(tmp_path: Path) -> TruyenVNSpider:
    """TruyenVNSpider with a temp output dir and fetch mocked out."""
    config = CrawlerConfig(output_dir=tmp_path / "output", log_level="DEBUG")
    return TruyenVNSpider(config=config)


@pytest.fixture
def parser() -> TruyenVNPageParser:
    return TruyenVNPageParser()


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------


class TestParseChapterNumberFromSlug:
    """Test chapter number extraction from Madara slugs."""

    def test_integer_chapter(self) -> None:
        assert parse_chapter_number_from_slug("chapter-10") == 10.0

    def test_full_url(self) -> None:
        url = "https://truyenvn.shop/truyen-tranh/my-manga/chapter-24/"
        assert parse_chapter_number_from_slug(url) == 24.0

    def test_decimal_chapter(self) -> None:
        assert parse_chapter_number_from_slug("chapter-10-5") == 10.5

    def test_chapter_zero(self) -> None:
        assert parse_chapter_number_from_slug("chapter-0") == 0.0

    def test_invalid_slug_raises(self) -> None:
        with pytest.raises(ParseError):
            parse_chapter_number_from_slug("not-a-chapter")


class TestAbsUrl:
    """Test URL resolution helper."""

    def test_absolute_url_unchanged(self) -> None:
        url = "https://example.com/path"
        assert abs_url(url) == url

    def test_relative_resolved(self) -> None:
        result = abs_url("/truyen-tranh/test")
        assert result.startswith("https://truyenvn.shop")


# ---------------------------------------------------------------------------
# Tests: Series parsing
# ---------------------------------------------------------------------------


class TestParseSeries:
    """Test series metadata + chapter list extraction."""

    def test_extracts_title(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert result["series"]["title"] == "Đồ Chơi XX Ở Công Trường Xây Dựng"

    def test_extracts_cover_url(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert "truyenvn.shop" in result["series"]["cover_url"]

    def test_extracts_synopsis(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert result["series"]["synopsis"] is not None
        assert "công nhân" in result["series"]["synopsis"].lower()

    def test_extracts_genres(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        genres = result["series"]["genres"]
        assert "Drama" in genres
        assert "Romance" in genres

    def test_extracts_status(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert result["series"]["status"] == "Ongoing"

    def test_extracts_author(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert result["series"]["author"] == "Test Author"

    def test_extracts_artist(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert result["series"]["artist"] == "Test Artist"

    def test_extracts_rating(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        assert result["series"]["rating"] == 8.5

    def test_extracts_chapters(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        chapters = result["chapters"]
        # 5 unique chapters (duplicate chapter 1 is deduped)
        assert len(chapters) == 5

    def test_chapters_sorted_by_number(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        numbers = [c["number"] for c in result["chapters"]]
        assert numbers == sorted(numbers)
        assert numbers == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_chapter_url_is_absolute(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(SERIES_PAGE_HTML)):
            result = spider.parse_series("https://truyenvn.shop/truyen-tranh/do-choi-xx/")

        for ch in result["chapters"]:
            assert ch["url"].startswith("https://")


# ---------------------------------------------------------------------------
# Tests: Chapter image extraction
# ---------------------------------------------------------------------------


class TestParseChapter:
    """Test chapter page image URL extraction."""

    def test_extracts_page_images(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.read_chapter("do-choi-xx", 1.0)

        # Should extract 3 images, filtering out: duplicate and logo
        assert len(pages) == 3

    def test_pages_numbered_sequentially(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.read_chapter("do-choi-xx", 1.0)

        page_numbers = [p["page_number"] for p in pages]
        assert page_numbers == [1, 2, 3]

    def test_pages_have_correct_metadata(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.read_chapter("do-choi-xx", 1.0)

        for page in pages:
            assert page["series_title"] == "Đồ Chơi XX Ở Công Trường Xây Dựng"
            assert page["chapter_number"] == 1.0
            assert page["local_path"] is None

    def test_filters_logo_images(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.read_chapter("do-choi-xx", 1.0)

        urls = [p["image_url"] for p in pages]
        assert not any("logo" in u for u in urls)

    def test_title_extracted_from_chapter_page(self, spider: TruyenVNSpider) -> None:
        """Title should be extracted from the <title> tag, not from slug."""
        with patch.object(spider, "_fetch", return_value=_mock_response(CHAPTER_PAGE_HTML)):
            pages = spider.read_chapter("do-choi-xx", 1.0)

        assert pages[0]["series_title"] == "Đồ Chơi XX Ở Công Trường Xây Dựng"


# ---------------------------------------------------------------------------
# Tests: Search / browse parsing
# ---------------------------------------------------------------------------


class TestExtractSeriesCards:
    """Test search result card extraction."""

    def test_extracts_unique_cards(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        # Should find 2 unique cards (deduping duplicate "manga-one")
        assert len(cards) == 2

    def test_card_has_title(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        assert cards[0]["title"] == "Manga One"
        assert cards[1]["title"] == "Manga Two"

    def test_card_has_url(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        assert "truyenvn.shop" in cards[0]["url"]
        assert "manga-one" in cards[0]["url"]

    def test_card_has_cover(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        assert cards[0]["cover_url"] is not None
        assert "cover1" in cards[0]["cover_url"]

    def test_card_has_latest_chapter(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        assert cards[0]["latest_chapter"] == 10.0
        assert cards[1]["latest_chapter"] == 25.0

    def test_card_has_status(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        assert cards[0]["status"] == "Ongoing"
        assert cards[1]["status"] == "Completed"

    def test_card_has_rating(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(SEARCH_PAGE_HTML)
        cards = parser.extract_series_cards(response)

        assert cards[0]["rating"] == 9.0
        assert cards[1]["rating"] == 7.5

    def test_empty_search_returns_empty(self, parser: TruyenVNPageParser) -> None:
        response = _mock_response(EMPTY_SEARCH_HTML)
        cards = parser.extract_series_cards(response)

        assert len(cards) == 0


class TestCrawlSearchLite:
    """Test search lite via spider."""

    def test_returns_results(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch_http", return_value=_mock_response(SEARCH_PAGE_HTML)):
            result = spider.search(name="test")

        assert len(result["results"]) == 2
        assert result["page"] == 1
        assert result["has_next_page"] is True

    def test_no_next_page_on_empty(self, spider: TruyenVNSpider) -> None:
        with patch.object(spider, "_fetch_http", return_value=_mock_response(EMPTY_SEARCH_HTML)):
            result = spider.search(name="nothing")

        assert len(result["results"]) == 0
        assert result["has_next_page"] is False


# ---------------------------------------------------------------------------
# Tests: Slug extraction
# ---------------------------------------------------------------------------


class TestSlugFromUrl:
    def test_standard_url(self) -> None:
        url = "https://truyenvn.shop/truyen-tranh/my-comic-slug/"
        assert TruyenVNSpider.slug_from_url(url) == "my-comic-slug"

    def test_url_without_trailing_slash(self) -> None:
        url = "https://truyenvn.shop/truyen-tranh/my-comic-slug"
        assert TruyenVNSpider.slug_from_url(url) == "my-comic-slug"


# ---------------------------------------------------------------------------
# Tests: SourceSpider protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_satisfies_source_spider(self) -> None:
        from comic_crawler.spiders.registry import SourceSpider

        spider = TruyenVNSpider()
        assert isinstance(spider, SourceSpider)

    def test_has_required_properties(self) -> None:
        spider = TruyenVNSpider()
        assert spider.name == "truyenvn"
        assert spider.base_url == "https://truyenvn.shop"

    def test_registered_in_default_registry(self) -> None:
        from comic_crawler.spiders.registry import create_default_registry

        registry = create_default_registry()
        assert registry.has("truyenvn")
        sources = registry.list_sources()
        names = [s["name"] for s in sources]
        assert "truyenvn" in names
        # Asura should still be there too
        assert "asura" in names
