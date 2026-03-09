"""Tests for the MangaDex spider (mocked HTTP responses)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comic_crawler.spiders.mangadex import MangaDexSpider
from comic_crawler.spiders.registry import SourceSpider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spider():
    return MangaDexSpider()


# ---------------------------------------------------------------------------
# Mock API responses
# ---------------------------------------------------------------------------

_MANGA_RESPONSE = {
    "result": "ok",
    "data": [
        {
            "id": "a1c7c817-4e59-43b7-9365-09675a149a6f",
            "type": "manga",
            "attributes": {
                "title": {"en": "One Piece"},
                "altTitles": [],
                "description": {"en": "A pirate adventure story."},
                "status": "ongoing",
                "tags": [
                    {
                        "id": "tag-1",
                        "attributes": {"name": {"en": "Action"}, "group": "genre"},
                    }
                ],
                "lastChapter": None,
            },
            "relationships": [
                {
                    "id": "cover-1",
                    "type": "cover_art",
                    "attributes": {"fileName": "cover.jpg"},
                },
                {
                    "id": "author-1",
                    "type": "author",
                    "attributes": {"name": "Oda Eiichiro"},
                },
            ],
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

_DETAIL_RESPONSE = {
    "result": "ok",
    "data": _MANGA_RESPONSE["data"][0],
}

_CHAPTER_FEED = {
    "result": "ok",
    "data": [
        {
            "id": "ch-uuid-1",
            "type": "chapter",
            "attributes": {
                "chapter": "1",
                "title": "Romance Dawn",
                "publishAt": "2020-01-01T00:00:00+00:00",
                "pages": 24,
                "translatedLanguage": "en",
            },
        },
        {
            "id": "ch-uuid-2",
            "type": "chapter",
            "attributes": {
                "chapter": "2",
                "title": "That Man, Straw Hat Luffy",
                "publishAt": "2020-01-08T00:00:00+00:00",
                "pages": 20,
                "translatedLanguage": "en",
            },
        },
    ],
    "total": 2,
    "limit": 100,
    "offset": 0,
}

_AT_HOME_RESPONSE = {
    "result": "ok",
    "baseUrl": "https://uploads.mangadex.org",
    "chapter": {
        "hash": "abc123hash",
        "data": ["page1.jpg", "page2.jpg", "page3.jpg"],
        "dataSaver": ["page1-saver.jpg"],
    },
}

_TAG_RESPONSE = {
    "result": "ok",
    "data": [
        {
            "id": "tag-action-uuid",
            "attributes": {"name": {"en": "Action"}, "group": "genre"},
        },
        {
            "id": "tag-romance-uuid",
            "attributes": {"name": {"en": "Romance"}, "group": "genre"},
        },
        {
            "id": "tag-theme-uuid",
            "attributes": {"name": {"en": "Isekai"}, "group": "theme"},
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMangaDexProtocol:
    def test_satisfies_source_spider_protocol(self, spider):
        assert isinstance(spider, SourceSpider)

    def test_name(self, spider):
        assert spider.name == "mangadex"

    def test_base_url(self, spider):
        assert spider.base_url == "https://mangadex.org"


class TestMangaDexSearch:
    @patch.object(MangaDexSpider, "_get_json", return_value=_MANGA_RESPONSE)
    def test_search_returns_results(self, mock_get, spider):
        result = spider.search(name="One Piece", page=1)
        assert result["page"] == 1
        assert result["series_count"] == 1
        assert len(result["results"]) == 1

        card = result["results"][0]
        assert card["title"] == "One Piece"
        assert card["slug"] == "a1c7c817-4e59-43b7-9365-09675a149a6f"
        assert "mangadex.org" in card["url"]
        assert card["cover_url"] is not None

    @patch.object(MangaDexSpider, "_get_json", return_value=_MANGA_RESPONSE)
    def test_search_pagination(self, mock_get, spider):
        result = spider.search(page=2)
        assert result["has_next_page"] is False


class TestMangaDexDetail:
    @patch.object(MangaDexSpider, "_get_json")
    def test_detail_returns_series_and_chapters(self, mock_get, spider):
        mock_get.side_effect = [_DETAIL_RESPONSE, _CHAPTER_FEED]

        result = spider.detail("a1c7c817-4e59-43b7-9365-09675a149a6f")

        assert result["series"]["title"] == "One Piece"
        assert result["series"]["author"] == "Oda Eiichiro"
        assert "Action" in result["series"]["genres"]
        assert result["series"]["synopsis"] == "A pirate adventure story."
        assert len(result["chapters"]) == 2
        assert result["chapters"][0]["number"] == 1.0
        assert result["chapters"][1]["number"] == 2.0

    @patch.object(MangaDexSpider, "_get_json")
    def test_detail_uses_cache(self, mock_get, spider):
        # Clear any stale cache from previous tests
        spider._detail_cache.clear()

        mock_get.side_effect = [_DETAIL_RESPONSE, _CHAPTER_FEED]
        slug = "a1c7c817-4e59-43b7-9365-09675a149a6f"

        result1 = spider.detail(slug)
        result2 = spider.detail(slug)  # should use cache

        assert result1 == result2
        assert mock_get.call_count == 2  # 1 manga + 1 feed (only first detail call)


class TestMangaDexReadChapter:
    @patch.object(MangaDexSpider, "_get_json")
    def test_read_chapter_constructs_image_urls(self, mock_get, spider):
        # Mock: find chapter ID, at-home, then detail for title
        mock_get.side_effect = [
            _CHAPTER_FEED,  # _find_chapter_id
            _AT_HOME_RESPONSE,  # at-home server
            _DETAIL_RESPONSE,  # _get_series_title → detail
            _CHAPTER_FEED,  # detail's _fetch_all_chapters
        ]

        pages = spider.read_chapter(
            "a1c7c817-4e59-43b7-9365-09675a149a6f", 1.0
        )

        assert len(pages) == 3
        assert pages[0]["page_number"] == 1
        assert "uploads.mangadex.org" in pages[0]["image_url"]
        assert "abc123hash" in pages[0]["image_url"]
        assert "page1.jpg" in pages[0]["image_url"]


class TestMangaDexCategories:
    @patch.object(MangaDexSpider, "_get_json", return_value=_TAG_RESPONSE)
    def test_categories_returns_genre_tags_only(self, mock_get, spider):
        cats = spider.categories()
        assert len(cats) == 2  # Action + Romance (Isekai is theme, filtered out)
        names = [c["name"] for c in cats]
        assert "Action" in names
        assert "Romance" in names
        assert "Isekai" not in names
