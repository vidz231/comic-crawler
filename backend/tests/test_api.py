"""Tests for the FastAPI API layer.

Uses ``httpx.AsyncClient`` with ``ASGITransport`` to test against the
real FastAPI app — no live server required.  The ``SpiderRegistry`` is
overridden at the FastAPI dependency level to return a mock registry.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from httpx import ASGITransport

from comic_crawler.api.app import create_app
from comic_crawler.api.dependencies import get_config, get_registry
from comic_crawler.api.routers import image_proxy as image_proxy_router
from comic_crawler.config import CrawlerConfig
from comic_crawler.spiders.registry import SpiderRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_SEARCH_RESULT = {
    "results": [
        {
            "title": "Solo Leveling",
            "slug": "solo-leveling-001",
            "url": "https://asuracomic.net/series/solo-leveling-001",
            "latest_chapter": 200.0,
            "cover_url": "https://img.example.com/cover.jpg",
            "status": "Ongoing",
            "rating": 9.7,
        },
    ],
    "page": 1,
    "has_next_page": True,
}

FAKE_DETAIL_RESULT = {
    "series": {
        "title": "Solo Leveling",
        "url": "https://asuracomic.net/series/solo-leveling-001",
        "cover_url": "https://img.example.com/cover.jpg",
        "author": "Chugong",
        "genres": ["Action", "Fantasy"],
        "status": "Completed",
        "synopsis": "A test synopsis.",
        "follower_count": 42000,
    },
    "chapters": [
        {
            "series_title": "Solo Leveling",
            "number": 1.0,
            "title": "Chapter 1",
            "url": "https://asuracomic.net/series/solo-leveling-001/chapter/1",
            "date_published": None,
            "page_count": 20,
        },
    ],
}

FAKE_CHAPTER_PAGES = [
    {
        "series_title": "Solo Leveling",
        "chapter_number": 1.0,
        "page_number": 1,
        "image_url": "https://img.example.com/page1.jpg",
        "local_path": None,
    },
    {
        "series_title": "Solo Leveling",
        "chapter_number": 1.0,
        "page_number": 2,
        "image_url": "https://img.example.com/page2.jpg",
        "local_path": None,
    },
]


def _make_mock_spider() -> MagicMock:
    """Create a mock spider with all protocol methods."""
    spider = MagicMock()
    spider.name = "asura"
    spider.base_url = "https://asuracomic.net"
    spider.search.return_value = FAKE_SEARCH_RESULT
    spider.detail.return_value = FAKE_DETAIL_RESULT
    spider.read_chapter.return_value = FAKE_CHAPTER_PAGES
    spider.categories.return_value = [
        {"name": "Action", "slug": "action"},
        {"name": "Fantasy", "slug": "fantasy"},
    ]
    return spider


def _make_mock_registry(spider: MagicMock | None = None) -> SpiderRegistry:
    """Build a SpiderRegistry with a mock spider injected."""
    if spider is None:
        spider = _make_mock_spider()
    registry = SpiderRegistry()
    # Bypass register() to avoid protocol checks on MagicMock
    registry._spiders["asura"] = spider
    # Also add a circuit breaker so list_sources_with_health works
    from comic_crawler.spiders.circuit_breaker import SourceCircuitBreaker
    registry._breakers["asura"] = SourceCircuitBreaker("asura")
    return registry


@pytest.fixture()
def mock_spider():
    """A fresh mock spider for each test."""
    return _make_mock_spider()


@pytest.fixture()
def app(mock_spider):
    """Create a fresh FastAPI app with the mock registry injected."""
    application = create_app()
    registry = _make_mock_registry(mock_spider)
    application.dependency_overrides[get_registry] = lambda: registry
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
async def client(app):
    """Async HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


# ---------------------------------------------------------------------------
# OpenAPI schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openapi_schema(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Comic Crawler API"
    assert "/api/v1/sources" in schema["paths"]
    assert "/api/v1/browse" in schema["paths"]
    assert "/api/v1/search" in schema["paths"]
    assert "/api/v1/comics/{source}/{slug}" in schema["paths"]
    assert "/api/v1/comics/{source}/{slug}/chapters/{number}" in schema["paths"]


# ---------------------------------------------------------------------------
# GET /api/v1/sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sources_list(client):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "asura"
    assert data["sources"][0]["base_url"] == "https://asuracomic.net"


# ---------------------------------------------------------------------------
# GET /api/v1/browse?source=asura
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browse_ok(client, mock_spider):
    resp = await client.get("/api/v1/browse", params={"source": "asura", "name": "solo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "asura"
    assert data["series_count"] == 1
    assert data["page"] == 1
    assert data["has_next_page"] is True
    assert data["results"][0]["title"] == "Solo Leveling"
    mock_spider.search.assert_called_once_with(name="solo", page=1, genre=None)


@pytest.mark.asyncio
async def test_browse_with_page(client, mock_spider):
    mock_spider.search.return_value = {
        "results": [],
        "page": 3,
        "has_next_page": False,
    }

    resp = await client.get("/api/v1/browse", params={"source": "asura", "page": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 3
    mock_spider.search.assert_called_once_with(name=None, page=3, genre=None)


@pytest.mark.asyncio
async def test_browse_missing_source(client):
    """Browse without source param → 422."""
    resp = await client.get("/api/v1/browse")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_browse_unknown_source(client):
    resp = await client.get("/api/v1/browse", params={"source": "nonexistent"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_single_source(client, mock_spider):
    resp = await client.get("/api/v1/search", params={"sources": "asura", "name": "solo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["sources_queried"] == ["asura"]
    assert len(data["results"]) == 1
    assert data["results"][0]["source"] == "asura"
    mock_spider.search.assert_called_once_with(name="solo", page=1, genre=None)


@pytest.mark.asyncio
async def test_search_all_sources(client, mock_spider):
    """Search without explicit sources queries all registered."""
    resp = await client.get("/api/v1/search", params={"name": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "asura" in data["sources_queried"]
    mock_spider.search.assert_called_once()


@pytest.mark.asyncio
async def test_search_unknown_source(client):
    """Search with unknown source gracefully returns empty results."""
    resp = await client.get("/api/v1/search", params={"sources": "unknown"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 0
    assert data["sources_queried"] == ["unknown"]
    assert data["results"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/comics/{source}/{slug}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comic_detail(client, mock_spider):
    resp = await client.get("/api/v1/comics/asura/solo-leveling-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "asura"
    assert data["slug"] == "solo-leveling-001"
    assert data["series"]["title"] == "Solo Leveling"
    assert len(data["chapters"]) == 1
    assert data["chapters"][0]["number"] == 1.0
    mock_spider.detail.assert_called_once_with("solo-leveling-001")


@pytest.mark.asyncio
async def test_comic_detail_unknown_source(client):
    resp = await client.get("/api/v1/comics/unknown/some-slug")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/comics/{source}/{slug}/chapters/{number}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chapter_read(client, mock_spider):
    resp = await client.get("/api/v1/comics/asura/solo-leveling-001/chapters/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "asura"
    assert data["series_title"] == "Solo Leveling"
    assert data["chapter_number"] == 1.0
    assert len(data["pages"]) == 2
    assert data["pages"][0]["image_url"] == "https://img.example.com/page1.jpg"
    mock_spider.read_chapter.assert_called_once_with("solo-leveling-001", 1.0)


@pytest.mark.asyncio
async def test_chapter_read_decimal(client, mock_spider):
    """Chapters with decimal numbers like 10.5 should work."""
    mock_spider.read_chapter.return_value = [
        {
            "series_title": "Test",
            "chapter_number": 10.5,
            "page_number": 1,
            "image_url": "https://img.example.com/p1.jpg",
        }
    ]

    resp = await client.get("/api/v1/comics/asura/test-series/chapters/10.5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["chapter_number"] == 10.5


@pytest.mark.asyncio
async def test_chapter_read_unknown_source(client):
    resp = await client.get("/api/v1/comics/unknown/slug/chapters/1")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_categories_single_source(client, mock_spider):
    resp = await client.get("/api/v1/categories", params={"source": "asura"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "asura"
    assert len(data[0]["categories"]) == 2
    assert data[0]["categories"][0]["slug"] == "action"
    mock_spider.categories.assert_called_once()


@pytest.mark.asyncio
async def test_categories_all_sources(client, mock_spider):
    resp = await client.get("/api/v1/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["source"] == "asura"


@pytest.mark.asyncio
async def test_categories_unknown_source(client):
    resp = await client.get("/api/v1/categories", params={"source": "unknown"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Browse / Search with genre
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browse_with_genre(client, mock_spider):
    resp = await client.get(
        "/api/v1/browse", params={"source": "asura", "genre": "action"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "asura"
    mock_spider.search.assert_called_once_with(name=None, page=1, genre="action")


@pytest.mark.asyncio
async def test_search_with_genre(client, mock_spider):
    resp = await client.get(
        "/api/v1/search", params={"sources": "asura", "genre": "fantasy"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources_queried"] == ["asura"]
    mock_spider.search.assert_called_once_with(name=None, page=1, genre="fantasy")


# ---------------------------------------------------------------------------
# GET /api/v1/image-proxy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_image_proxy_allows_khotruyen_and_passes_configured_proxies(
    client, app, monkeypatch
):
    captured: dict[str, object] = {}

    def _fake_fetch_image(url: str, referer: str | None, proxy_list: list[str]):
        captured["url"] = url
        captured["referer"] = referer
        captured["proxy_list"] = proxy_list
        return b"image-bytes", 200, "image/jpeg"

    app.dependency_overrides[get_config] = lambda: CrawlerConfig(
        proxy_list=["http://proxy.example:8080"]
    )
    monkeypatch.setattr(image_proxy_router, "_fetch_image", _fake_fetch_image)

    resp = await client.get(
        "/api/v1/image-proxy",
        params={
            "url": (
                "https://khotruyen.ac/wp-content/uploads/2024/01/"
                "truyen-thuc-tap-o-lang-tien-ca.jpg"
            )
        },
    )

    assert resp.status_code == 200
    assert resp.content == b"image-bytes"
    assert resp.headers["content-type"] == "image/jpeg"
    assert captured["url"] == (
        "https://khotruyen.ac/wp-content/uploads/2024/01/"
        "truyen-thuc-tap-o-lang-tien-ca.jpg"
    )
    assert captured["referer"] == "https://khotruyen.ac/"
    assert captured["proxy_list"] == ["http://proxy.example:8080"]
