"""Tests for the MangaKakalot spider (mocked HTTP responses)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from comic_crawler.spiders.mangakakalot import MangaKakalotSpider
from comic_crawler.spiders.mangakakalot_parser import MangaKakalotPageParser
from comic_crawler.spiders.registry import SourceSpider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spider():
    return MangaKakalotSpider()


# ---------------------------------------------------------------------------
# Mock HTML responses (Adaptor-like objects)
# ---------------------------------------------------------------------------


class FakeElement:
    """Minimal mock of a scrapling Adaptor element."""

    def __init__(self, text="", attrib=None, children=None):
        self.text = text
        self.attrib = attrib or {}
        self._children = children or []

    def css(self, selector):
        return self._children


class FakeResponse:
    """Minimal mock of a scrapling Adaptor response."""

    def __init__(self, search_cards=None, detail_elements=None):
        self._search_cards = search_cards or []
        self._detail = detail_elements or {}

    def css(self, selector):
        return self._detail.get(selector, [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMangaKakalotProtocol:
    def test_satisfies_source_spider_protocol(self, spider):
        assert isinstance(spider, SourceSpider)

    def test_name(self, spider):
        assert spider.name == "mangakakalot"

    def test_base_url(self, spider):
        assert spider.base_url == "https://www.manganato.gg"


class TestMangaKakalotCategories:
    def test_categories_returns_list(self, spider):
        cats = spider.categories()
        assert len(cats) > 0
        assert all("name" in c and "slug" in c for c in cats)
        names = [c["name"] for c in cats]
        assert "Action" in names
        assert "Romance" in names

    def test_supports_multi_genre_is_false(self, spider):
        assert spider.supports_multi_genre is False


class TestMangaKakalotSearch:
    @patch.object(MangaKakalotSpider, "_search_json_api")
    def test_search_by_name(self, mock_search_api, spider):
        """Verify search via JSON API (primary path)."""
        mock_search_api.return_value = {
            "results": [
                {
                    "title": "One Piece",
                    "slug": "one-piece",
                    "url": "https://www.manganato.gg/manga/one-piece",
                    "cover_url": "https://img.manganato.gg/cover.jpg",
                    "author": "Oda",
                    "latest_chapter": 1176.0,
                    "source": "mangakakalot",
                }
            ],
            "page": 1,
            "has_next_page": False,
            "series_count": 1,
        }

        result = spider.search(name="One Piece", page=1)

        assert result["page"] == 1
        assert result["has_next_page"] is False
        assert isinstance(result["results"], list)
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "One Piece"

    @patch.object(MangaKakalotSpider, "_fetch_listing")
    def test_search_by_genre(self, mock_fetch, spider):
        mock_response = FakeResponse()
        mock_fetch.return_value = mock_response

        with (
            patch.object(spider._parser, "extract_search_cards", return_value=[]),
            patch.object(spider._parser, "extract_has_next_page", return_value=False),
        ):
            result = spider.search(genre="action", page=1)

        assert result["page"] == 1


class TestMangaKakalotDetail:
    @patch.object(MangaKakalotSpider, "_fetch_chapters_api", return_value=[
        {"series_title": "One Piece", "number": 1176.0, "title": "Chapter 1176",
         "url": "https://www.manganato.gg/manga/one-piece/chapter-1176",
         "date_published": "2026-03-06T02:47:24.000000Z", "page_count": None},
    ])
    @patch.object(MangaKakalotSpider, "_fetch_series")
    def test_detail_returns_series_data(self, mock_fetch, mock_chapters, spider):
        mock_response = FakeResponse()
        mock_fetch.return_value = mock_response

        with (
            patch.object(spider._parser, "extract_series_title", return_value="One Piece"),
            patch.object(spider._parser, "extract_synopsis", return_value="A story"),
            patch.object(spider._parser, "extract_cover_url", return_value="http://cover.jpg"),
            patch.object(spider._parser, "extract_author", return_value="Oda"),
            patch.object(spider._parser, "extract_genres", return_value=["Action"]),
            patch.object(spider._parser, "extract_status", return_value="Ongoing"),
        ):
            result = spider.detail("one-piece")

        assert result["series"]["title"] == "One Piece"
        assert result["series"]["author"] == "Oda"
        assert isinstance(result["chapters"], list)
        assert len(result["chapters"]) == 1
        assert result["chapters"][0]["number"] == 1176.0


class TestMangaKakalotURLHelpers:
    def test_slug_to_url(self):
        """All slugs now use the same /manga/{slug} pattern."""
        url = MangaKakalotSpider._slug_to_url("one-piece")
        assert url == "https://www.manganato.gg/manga/one-piece"

    def test_slug_to_url_with_dashes(self):
        url = MangaKakalotSpider._slug_to_url("tales-of-demons-and-gods")
        assert url == "https://www.manganato.gg/manga/tales-of-demons-and-gods"

    def test_build_chapter_url(self):
        url = MangaKakalotSpider._build_chapter_url("one-piece", "5")
        assert url == "https://www.manganato.gg/manga/one-piece/chapter-5"

    def test_build_chapter_url_with_decimal(self):
        url = MangaKakalotSpider._build_chapter_url("one-piece", "10.5")
        assert url == "https://www.manganato.gg/manga/one-piece/chapter-10.5"


class TestMangaKakalotParser:
    def test_slug_from_url_new_gg(self):
        slug = MangaKakalotPageParser._slug_from_url(
            "https://www.mangakakalot.gg/manga/one-piece"
        )
        assert slug == "one-piece"

    def test_slug_from_url_manganato_gg(self):
        slug = MangaKakalotPageParser._slug_from_url(
            "https://www.manganato.gg/manga/solo-leveling"
        )
        assert slug == "solo-leveling"
