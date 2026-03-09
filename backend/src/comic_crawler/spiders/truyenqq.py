"""TruyenQQ (truyenqqno.com) spider — crawl series listings, metadata, and chapter images.

Thin orchestrator that delegates parsing to ``TruyenQQPageParser`` and
search to ``TruyenQQSearcher``.
Implements the ``SourceSpider`` protocol for the spider registry.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from cachetools import TTLCache

from comic_crawler.spiders.base_fetcher import BaseFetcher

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger
from comic_crawler.spiders.truyenqq_parser import (
    BASE_URL,
    MANGA_PATH,
    TruyenQQPageParser,
    abs_url,
    parse_chapter_number_from_url,
    slug_from_url,
)
from comic_crawler.spiders.truyenqq_search import TruyenQQSearcher

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# TruyenQQSpider
# ---------------------------------------------------------------------------


class TruyenQQSpider(BaseFetcher):
    """Concrete spider for truyenqqno.com.

    Inherits ``_fetch``, ``_fetch_chapter``, ``_fetch_series``,
    ``_fetch_listing`` from :class:`BaseFetcher`.
    Implements the ``SourceSpider`` protocol so it can be registered
    in the ``SpiderRegistry`` and served by the API.
    """

    name = "truyenqq"
    base_url = BASE_URL

    # Map genre slug → TruyenQQ URL segment (slug-id).
    GENRE_MAP: dict[str, str] = {
        "action": "action-26", "adventure": "adventure-27",
        "anime": "anime-62", "chuyen-sinh": "chuyen-sinh-91",
        "co-dai": "co-dai-90", "comedy": "comedy-28",
        "comic": "comic-60", "demons": "demons-99",
        "detective": "detective-100", "doujinshi": "doujinshi-96",
        "drama": "drama-29", "fantasy": "fantasy-30",
        "gender-bender": "gender-bender-45", "harem": "harem-47",
        "historical": "historical-51", "horror": "horror-44",
        "huyen-huyen": "huyen-huyen-468", "isekai": "isekai-85",
        "josei": "josei-54", "mafia": "mafia-69",
        "magic": "magic-58", "manga": "manga-469",
        "manhua": "manhua-35", "manhwa": "manhwa-49",
        "martial-arts": "martial-arts-41", "military": "military-101",
        "mystery": "mystery-39", "ngon-tinh": "ngon-tinh-87",
        "one-shot": "one-shot-95", "psychological": "psychological-40",
        "romance": "romance-36", "school-life": "school-life-37",
        "sci-fi": "sci-fi-43", "seinen": "seinen-42",
        "shoujo": "shoujo-38", "shoujo-ai": "shoujo-ai-98",
        "shounen": "shounen-31", "shounen-ai": "shounen-ai-86",
        "slice-of-life": "slice-of-life-46", "sports": "sports-57",
        "supernatural": "supernatural-32", "tragedy": "tragedy-52",
        "trong-sinh": "trong-sinh-82", "truyen-mau": "truyen-mau-92",
        "webtoon": "webtoon-55", "xuyen-khong": "xuyen-khong-88",
    }

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        self._config = config or CrawlerConfig()
        self._log = get_logger(f"spider.{self.name}")
        self._parser = TruyenQQPageParser()
        self._searcher = TruyenQQSearcher(self, self._config, self._parser)
        # In-memory caches — same TTLs as AsuraSpider.
        self._detail_cache: TTLCache[str, dict] = TTLCache(maxsize=100, ttl=600)
        self._chapter_cache: TTLCache[str, list] = TTLCache(maxsize=200, ttl=1800)

    # TruyenQQ is fully server-rendered — no JavaScript needed.
    _USE_HTTP_FETCH = True

    # Periods supported by trending() — router validates against this list.
    trending_periods: list[str] = ["daily", "weekly", "monthly"]

    # Maps API period names → TruyenQQ top page URLs.
    _TRENDING_URL_MAP: dict[str, str] = {
        "daily": f"{BASE_URL}/top-ngay.html",
        "weekly": f"{BASE_URL}/top-tuan.html",
        "monthly": f"{BASE_URL}/top-thang.html",
    }

    # -- Slug helpers ----------------------------------------------------------

    @staticmethod
    def slug_from_url(url: str) -> str:
        """Extract the series slug from a TruyenQQ URL.

        Example: ``/truyen-tranh/cau-be-cua-than-chet-9441`` → ``cau-be-cua-than-chet-9441``
        """
        return slug_from_url(url)

    # -- SourceSpider protocol ---------------------------------------------

    def categories(self) -> list[dict[str, str]]:
        """Return available genres — implements ``SourceSpider.categories``."""
        return [
            {"name": slug.replace("-", " ").title(), "slug": slug}
            for slug in self.GENRE_MAP
        ]

    @property
    def supports_multi_genre(self) -> bool:
        """TruyenQQ uses path-based genre URLs — single genre only."""
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
        url = f"{BASE_URL}{MANGA_PATH}/{slug}"
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
            else str(chapter_number)
        )
        chapter_url = f"{BASE_URL}{MANGA_PATH}/{slug}-chap-{ch_str}.html"

        self._log.info("read_chapter", url=chapter_url)
        response = self._fetch(chapter_url)

        try:
            series_title = self._parser.extract_title_from_chapter_page(response)
        except ParseError:
            # Fallback: use slug as title
            self._log.warning("chapter_title_fallback", slug=slug)
            # Remove numeric ID suffix and format as title
            clean_slug = re.sub(r"-\d+$", "", slug)
            series_title = clean_slug.replace("-", " ").title()

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
            "artist": None,  # TruyenQQ doesn't separate artist from author
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

    def trending(self, period: str = "daily") -> list[dict[str, Any]]:
        """Fetch trending comics.  Implements ``SourceSpider.trending``.

        Args:
            period: One of ``trending_periods``.  Validated by the API layer.

        Returns:
            List of TrendingItem-shaped dicts with rank, title, slug, url,
            cover_url, rating, view_count, latest_chapter.
        """
        self._log.info("trending", period=period)
        url = self._TRENDING_URL_MAP[period]
        response = self._fetch_listing(url)
        return self._parser.extract_trending_cards(response)
