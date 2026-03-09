"""TruyenVN.shop spider — crawl series listings, metadata, and chapter images.

Thin orchestrator that delegates parsing to ``TruyenVNPageParser`` and
search to ``TruyenVNSearcher``.
Implements the ``SourceSpider`` protocol for the spider registry.
"""

from __future__ import annotations

import json
import re
from typing import Any

from cachetools import TTLCache
from urllib.parse import urlparse

from comic_crawler.spiders.base_fetcher import BaseFetcher

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger
from comic_crawler.spiders.truyenvn_parser import (
    BASE_URL,
    MANGA_PATH,
    TruyenVNPageParser,
    abs_url,
    parse_chapter_number_from_slug,
)
from comic_crawler.spiders.truyenvn_search import TruyenVNSearcher
from comic_crawler.storage import sanitize_filename

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# TruyenVNSpider
# ---------------------------------------------------------------------------


class TruyenVNSpider(BaseFetcher):
    """Concrete spider for truyenvn.shop (Madara WordPress Theme).

    Inherits ``_fetch``, ``_fetch_chapter``, ``_fetch_series``,
    ``_fetch_listing`` from :class:`BaseFetcher`.
    The three selector constants below are tuned for the Madara WP DOM.

    Implements the ``SourceSpider`` protocol so it can be registered
    in the ``SpiderRegistry`` and served by the API.
    """

    name = "truyenvn"
    base_url = BASE_URL

    # Map genre slug → TruyenVN URL slug.
    GENRE_MAP: dict[str, str] = {
        "truyen-tranh-18": "truyen-tranh-18",
        "manhwa": "manhwa", "manhua": "manhua", "action": "action",
        "romance": "romance", "drama": "drama",
        "adventure": "adventure", "historical": "historical",
        "huyen-huyen": "huyen-huyen", "kinh-di": "kinh-di",
        "hien-dai": "hien-dai", "horror": "horror",
        "hoc-duong": "hoc-duong", "harem": "harem",
        "game": "game", "echi": "echi",
        "fantasy": "fantasy", "comic": "comic",
        "cooking": "cooking", "dam-my": "dam-my",
        "boylove": "boylove",
    }

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        self._config = config or CrawlerConfig()
        self._log = get_logger(f"spider.{self.name}")
        self._parser = TruyenVNPageParser()
        self._searcher = TruyenVNSearcher(self, self._config, self._parser)
        # In-memory caches — same TTLs as AsuraSpider.
        self._detail_cache: TTLCache[str, dict] = TTLCache(maxsize=100, ttl=600)
        self._chapter_cache: TTLCache[str, list] = TTLCache(maxsize=200, ttl=1800)

    # TruyenVN (Madara WP) is fully server-rendered — no JavaScript needed.
    # Use curl_cffi (plain HTTP with browser headers) instead of Playwright.
    # This avoids ERR_CONNECTION_CLOSED on the search endpoint and is ~10-30x faster.
    _USE_HTTP_FETCH = True

    # CSS selectors are unused in HTTP mode (no browser DOM to wait on).

    # Periods supported by trending() — router validates against this list.
    trending_periods: list[str] = ["trending", "views", "rating", "new"]

    # Maps API period names → Madara ``m_orderby`` query param values.
    _TRENDING_PERIOD_MAP: dict[str, str] = {
        "trending": "trending",
        "views":    "views",
        "rating":   "rating",
        "new":      "new-manga",
    }

    # -- Slug helpers ----------------------------------------------------------

    @staticmethod
    def slug_from_url(url: str) -> str:
        """Extract the series slug from a TruyenVN URL.

        Example: ``/truyen-tranh/my-comic-slug/`` → ``my-comic-slug``
        """
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parts[0] == "truyen-tranh":
            return parts[1]
        if len(parts) == 1:
            return parts[0]
        raise ParseError(f"Cannot extract slug from URL: {url}", url=url)

    # -- SourceSpider protocol ---------------------------------------------

    def categories(self) -> list[dict[str, str]]:
        """Return available genres — implements ``SourceSpider.categories``."""
        return [
            {"name": slug.replace("-", " ").title(), "slug": slug}
            for slug in self.GENRE_MAP
        ]

    @property
    def supports_multi_genre(self) -> bool:
        """TruyenVN uses path-based genre URLs — single genre only."""
        return False

    def search(
        self,
        *,
        name: str | None = None,
        page: int = 1,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Paginated search — implements ``SourceSpider.search``."""
        return self._searcher.crawl_search_lite(page=page, name=name, genre=genre)

    def detail(self, slug: str) -> dict[str, Any]:
        """Full series detail — implements ``SourceSpider.detail``."""
        if slug in self._detail_cache:
            return self._detail_cache[slug]
        url = f"{BASE_URL}{MANGA_PATH}/{slug}/"
        result = self.parse_series(url)
        self._detail_cache[slug] = result
        return result

    def read_chapter(
        self,
        slug: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Chapter page images — implements ``SourceSpider.read_chapter``.

        Extracts the series title from the chapter page's <title> tag
        to avoid a redundant full series page fetch.
        """
        cache_key = f"{slug}:{chapter_number}"
        if cache_key in self._chapter_cache:
            return self._chapter_cache[cache_key]

        ch_str = (
            str(int(chapter_number))
            if chapter_number == int(chapter_number)
            else str(chapter_number).replace(".", "-")
        )
        chapter_url = f"{BASE_URL}{MANGA_PATH}/{slug}/chapter-{ch_str}/"

        self._log.info("read_chapter", url=chapter_url)
        response = self._fetch(chapter_url)

        try:
            series_title = self._parser.extract_title_from_chapter_page(response)
        except ParseError:
            # Fallback: use slug as title
            self._log.warning("chapter_title_fallback", slug=slug)
            series_title = slug.replace("-", " ").title()

        pages = self._parser.extract_page_images(
            response, series_title, chapter_number
        )

        self._log.info(
            "chapter_parsed",
            url=chapter_url,
            chapter=chapter_number,
            page_count=len(pages),
        )
        self._chapter_cache[cache_key] = pages
        return pages

    # -- Full series parse (used by detail()) ------------------------------

    def parse_series(self, url: str) -> dict[str, Any]:
        """Fetch a series page and extract metadata + chapter list.

        Args:
            url: Full URL to the series page.

        Returns:
            Dict with ``series`` (metadata dict) and ``chapters``
            (list of chapter dicts).
        """
        self._log.info("parse_series", url=url)
        response = self._fetch(url)

        title = self._parser.extract_series_title(response)
        synopsis = self._parser.extract_synopsis(response)
        cover_url = self._parser.extract_cover_url(response)

        series_data = {
            "title": title,
            "url": url,
            "cover_url": cover_url,
            "synopsis": synopsis,
            "author": self._parser.extract_author(response),
            "artist": self._parser.extract_artist(response),
            "genres": self._parser.extract_genres(response),
            "status": self._parser.extract_status(response),
            "rating": self._parser.extract_rating(response),
        }

        chapters = self._parser.extract_chapter_list(response, title, url)

        self._log.info(
            "series_parsed",
            title=title,
            chapter_count=len(chapters),
        )

        return {
            "series": series_data,
            "chapters": chapters,
        }

    # -- SourceSpider: trending ------------------------------------------------

    def trending(self, period: str = "trending") -> list[dict[str, Any]]:
        """Fetch trending comics.  Implements ``SourceSpider.trending``.

        Args:
            period: One of ``trending_periods``.  Validated by the API layer.

        Returns:
            List of TrendingItem-shaped dicts with rank, title, slug, url,
            cover_url, rating, view_count, latest_chapter.
        """
        self._log.info("trending", period=period)
        orderby = self._TRENDING_PERIOD_MAP[period]
        url = f"{BASE_URL}{MANGA_PATH}/?m_orderby={orderby}"
        response = self._fetch_listing(url)
        return self._parser.extract_trending_cards(response)
