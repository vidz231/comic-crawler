"""Tests for the SpiderRegistry and SourceSpider protocol."""

from __future__ import annotations

import pytest

from comic_crawler.config import CrawlerConfig
from comic_crawler.spiders.registry import (
    SourceSpider,
    SpiderRegistry,
    create_default_registry,
)


# ---------------------------------------------------------------------------
# Stub spider for testing
# ---------------------------------------------------------------------------


class FakeSpider:
    """Minimal stub that satisfies the SourceSpider protocol."""

    name = "fake"
    base_url = "https://fake.example.com"

    def search(self, *, name=None, page=1, genre=None):
        return {
            "results": [{"title": "Fake Comic", "url": "https://fake.example.com/series/fake-1"}],
            "page": page,
            "has_next_page": False,
        }

    def detail(self, slug):
        return {
            "series": {"title": "Fake Comic", "url": f"https://fake.example.com/series/{slug}"},
            "chapters": [],
        }

    def read_chapter(self, slug, chapter_number):
        return [
            {
                "series_title": "Fake Comic",
                "chapter_number": chapter_number,
                "page_number": 1,
                "image_url": "https://fake.example.com/page1.jpg",
            }
        ]

    def categories(self):
        return [{"name": "Action", "slug": "action"}]

    @property
    def supports_multi_genre(self):
        return False


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestSpiderRegistry:
    def test_register_and_get(self):
        registry = SpiderRegistry()
        spider = FakeSpider()
        registry.register(spider)
        assert registry.get("fake") is spider

    def test_get_unknown_raises(self):
        registry = SpiderRegistry()
        with pytest.raises(KeyError, match="Unknown source"):
            registry.get("nonexistent")

    def test_duplicate_registration_raises(self):
        registry = SpiderRegistry()
        registry.register(FakeSpider())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(FakeSpider())

    def test_list_sources(self):
        registry = SpiderRegistry()
        registry.register(FakeSpider())
        sources = registry.list_sources()
        assert len(sources) == 1
        assert sources[0]["name"] == "fake"
        assert sources[0]["base_url"] == "https://fake.example.com"

    def test_has(self):
        registry = SpiderRegistry()
        registry.register(FakeSpider())
        assert registry.has("fake") is True
        assert registry.has("unknown") is False


class TestDefaultRegistry:
    def test_contains_asura(self):
        registry = create_default_registry()
        assert registry.has("asura")
        sources = registry.list_sources()
        names = [s["name"] for s in sources]
        assert "asura" in names

    def test_asura_satisfies_protocol(self):
        registry = create_default_registry()
        spider = registry.get("asura")
        assert isinstance(spider, SourceSpider)


class TestSourceSpiderProtocol:
    def test_fake_spider_satisfies_protocol(self):
        assert isinstance(FakeSpider(), SourceSpider)
