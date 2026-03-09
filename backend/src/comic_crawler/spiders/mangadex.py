"""MangaDex spider — public JSON API, no scraping needed.

Uses the MangaDex API v5 (https://api.mangadex.org) to search, fetch
series details, chapter lists, and page images.

API reference: https://api.mangadex.org/docs/

.. note::

   MangaDex requires attribution.  The ``credits`` property exposes
   the required notice for consumers of this spider.
"""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import FetchError
from comic_crawler.logging import get_logger
from comic_crawler.spiders.http_json_spider import HttpJsonSpider

log = get_logger(__name__)

# Auto-discovery marker — the registry picks this up automatically
SPIDER_CLASS: type | None = None  # set at module bottom after class definition

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COVER_BASE = "https://uploads.mangadex.org/covers"
_LANG = "en"  # Default content language


# ---------------------------------------------------------------------------
# MangaDexSpider
# ---------------------------------------------------------------------------


class MangaDexSpider(HttpJsonSpider):
    """Concrete spider for MangaDex (api.mangadex.org).

    MangaDex provides a free, public JSON REST API.  This spider uses
    ``HttpJsonSpider._get_json`` for all requests — no HTML parsing or
    Playwright needed.
    """

    _BASE_API_URL = "https://api.mangadex.org"
    _EXTRA_HEADERS: dict[str, str] = {}  # noqa: RUF012

    # -- Cache (in-memory TTL) ---------------------------------------------
    _detail_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=256, ttl=600)
    _chapter_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(maxsize=256, ttl=1800)

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        super().__init__(config=config)
        # Apply per-source rate limit if configured
        src_limits = self._config.source_rate_limits
        if "mangadex" in src_limits:
            self._download_delay = src_limits["mangadex"]
        else:
            # MangaDex asks for reasonable rate limits
            self._download_delay = max(self._download_delay, 0.3)

    # -- SourceSpider protocol properties ----------------------------------

    @property
    def name(self) -> str:
        return "mangadex"

    @property
    def base_url(self) -> str:
        return "https://mangadex.org"

    @property
    def supports_multi_genre(self) -> bool:
        return True

    @property
    def credits(self) -> str:
        return (
            "Powered by MangaDex (https://mangadex.org). "
            "All content belongs to their respective creators."
        )

    # -- Categories --------------------------------------------------------

    def categories(self) -> list[dict[str, str]]:
        """Fetch all MangaDex tags (genres)."""
        data = self._get_json("/manga/tag")
        tags: list[dict[str, str]] = []
        for tag in data.get("data", []):
            attrs = tag.get("attributes", {})
            name_map = attrs.get("name", {})
            name = name_map.get("en", "")
            if name and attrs.get("group") == "genre":
                tags.append({"name": name, "slug": tag["id"]})
        return sorted(tags, key=lambda t: t["name"])

    # -- Search / browse ---------------------------------------------------

    def search(
        self,
        *,
        name: str | None = None,
        page: int = 1,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Search MangaDex for manga titles."""
        limit = 20
        offset = (page - 1) * limit

        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art"],
            "availableTranslatedLanguage[]": [_LANG],
            "order[relevance]": "desc",
            "contentRating[]": ["safe", "suggestive"],
        }

        if name:
            params["title"] = name
        if genre:
            # genre is a UUID tag id
            params["includedTags[]"] = [genre]

        data = self._get_json("/manga", params=params)

        total = data.get("total", 0)
        results = [self._manga_to_card(m) for m in data.get("data", [])]

        return {
            "results": results,
            "page": page,
            "has_next_page": offset + limit < total,
            "series_count": total,
        }

    # -- Detail ------------------------------------------------------------

    def detail(self, slug: str) -> dict[str, Any]:
        """Fetch full series detail by MangaDex manga UUID."""
        cached = self._detail_cache.get(slug)
        if cached is not None:
            return cached

        # Fetch manga metadata
        manga_data = self._get_json(
            f"/manga/{slug}",
            params={"includes[]": ["cover_art", "author", "artist"]},
        )
        manga = manga_data.get("data", {})

        # Fetch chapters (English only, sorted by chapter number)
        chapters = self._fetch_all_chapters(slug)

        series = self._manga_to_series(manga)
        chapter_list = [self._chapter_to_dict(ch) for ch in chapters]

        result: dict[str, Any] = {
            "series": series,
            "chapters": chapter_list,
        }
        self._detail_cache[slug] = result
        return result

    # -- Chapter read ------------------------------------------------------

    def read_chapter(
        self,
        slug: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Fetch page image URLs for a chapter.

        MangaDex requires a two-step process:
        1. Get the English chapter ID from the manga feed
        2. Call /at-home/server/{chapterId} for image URLs
        """
        cache_key = f"{slug}:{chapter_number}"
        cached = self._chapter_cache.get(cache_key)
        if cached is not None:
            return cached

        # Find the chapter ID
        chapter_id = self._find_chapter_id(slug, chapter_number)
        if not chapter_id:
            raise FetchError(
                f"Chapter {chapter_number} not found for manga {slug}",
                url=f"{self._BASE_API_URL}/manga/{slug}/feed",
            )

        # Get the at-home server + image filenames
        server_data = self._get_json(f"/at-home/server/{chapter_id}")
        base_url = server_data.get("baseUrl", "")
        ch_hash = server_data.get("chapter", {}).get("hash", "")
        filenames = server_data.get("chapter", {}).get("data", [])

        # Get series title for the response
        series_title = self._get_series_title(slug)

        pages: list[dict[str, Any]] = []
        for idx, filename in enumerate(filenames, start=1):
            pages.append({
                "series_title": series_title,
                "chapter_number": chapter_number,
                "page_number": idx,
                "image_url": f"{base_url}/data/{ch_hash}/{filename}",
            })

        self._chapter_cache[cache_key] = pages
        return pages

    # -- Trending ----------------------------------------------------------

    @property
    def trending_periods(self) -> list[str]:
        return ["today", "weekly", "monthly", "all"]

    def trending(self, period: str = "today") -> list[dict[str, Any]]:
        """Fetch popular manga sorted by follows."""
        order_map: dict[str, dict[str, str]] = {
            "today": {"order[followedCount]": "desc"},
            "weekly": {"order[followedCount]": "desc"},
            "monthly": {"order[followedCount]": "desc"},
            "all": {"order[followedCount]": "desc"},
        }

        params: dict[str, Any] = {
            "limit": 20,
            "includes[]": ["cover_art"],
            "availableTranslatedLanguage[]": [_LANG],
            "contentRating[]": ["safe", "suggestive"],
            **order_map.get(period, order_map["today"]),
        }

        # For "today"/"weekly", add createdAtSince filter
        if period == "today":
            params["createdAtSince"] = self._days_ago(1)
        elif period == "weekly":
            params["createdAtSince"] = self._days_ago(7)
        elif period == "monthly":
            params["createdAtSince"] = self._days_ago(30)

        data = self._get_json("/manga", params=params)

        items: list[dict[str, Any]] = []
        for rank, manga in enumerate(data.get("data", []), start=1):
            card = self._manga_to_card(manga)
            card["rank"] = rank
            items.append(card)

        return items

    # =====================================================================
    # Internal helpers
    # =====================================================================

    def _manga_to_card(self, manga: dict[str, Any]) -> dict[str, Any]:
        """Convert a MangaDex manga object to a search card dict."""
        attrs = manga.get("attributes", {})
        manga_id = manga.get("id", "")

        title = self._extract_title(attrs)
        cover_url = self._extract_cover_url(manga)

        return {
            "title": title,
            "slug": manga_id,
            "url": f"https://mangadex.org/title/{manga_id}",
            "cover_url": cover_url,
            "status": attrs.get("status"),
            "rating": None,
            "latest_chapter": self._parse_chapter_number(attrs.get("lastChapter")),
        }

    def _manga_to_series(self, manga: dict[str, Any]) -> dict[str, Any]:
        """Convert a MangaDex manga object to a full series dict."""
        attrs = manga.get("attributes", {})
        manga_id = manga.get("id", "")

        title = self._extract_title(attrs)
        cover_url = self._extract_cover_url(manga)

        # Extract author/artist from relationships
        author = ""
        for rel in manga.get("relationships", []):
            if rel.get("type") == "author":
                author = rel.get("attributes", {}).get("name", "")
                break

        # Extract genres
        genres = []
        for tag in attrs.get("tags", []):
            tag_name = tag.get("attributes", {}).get("name", {}).get("en", "")
            if tag_name:
                genres.append(tag_name)

        # Synopsis
        desc = attrs.get("description", {})
        synopsis = desc.get("en", "") if isinstance(desc, dict) else str(desc)

        return {
            "title": title,
            "url": f"https://mangadex.org/title/{manga_id}",
            "cover_url": cover_url,
            "author": author,
            "genres": genres,
            "status": attrs.get("status"),
            "synopsis": synopsis,
        }

    def _chapter_to_dict(self, chapter: dict[str, Any]) -> dict[str, Any]:
        """Convert a MangaDex chapter to our chapter dict format."""
        attrs = chapter.get("attributes", {})
        ch_id = chapter.get("id", "")

        number_str = attrs.get("chapter", "0")
        try:
            number = float(number_str) if number_str else 0.0
        except (ValueError, TypeError):
            number = 0.0

        return {
            "series_title": "",  # filled by caller
            "number": number,
            "title": attrs.get("title") or f"Chapter {number_str}",
            "url": f"https://mangadex.org/chapter/{ch_id}",
            "date_published": attrs.get("publishAt"),
            "page_count": attrs.get("pages"),
        }

    def _fetch_all_chapters(self, manga_id: str) -> list[dict[str, Any]]:
        """Paginate through all English chapters of a manga."""
        all_chapters: list[dict[str, Any]] = []
        offset = 0
        limit = 100
        # Deduplicate by chapter number across all pages (keep first upload)
        seen: set[str] = set()

        while True:
            data = self._get_json(
                f"/manga/{manga_id}/feed",
                params={
                    "translatedLanguage[]": [_LANG],
                    "order[chapter]": "asc",
                    "limit": limit,
                    "offset": offset,
                    "includes[]": ["scanlation_group"],
                    "contentRating[]": ["safe", "suggestive", "erotica"],
                },
            )
            chapters = data.get("data", [])
            if not chapters:
                break

            for ch in chapters:
                ch_num = ch.get("attributes", {}).get("chapter", "")
                if ch_num not in seen:
                    seen.add(ch_num)
                    all_chapters.append(ch)

            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break

        return all_chapters

    def _find_chapter_id(self, manga_id: str, chapter_number: float) -> str | None:
        """Look up the MangaDex chapter UUID for a given chapter number."""
        ch_str = (
            str(int(chapter_number))
            if chapter_number == int(chapter_number)
            else str(chapter_number)
        )

        data = self._get_json(
            f"/manga/{manga_id}/feed",
            params={
                "translatedLanguage[]": [_LANG],
                "chapter[]": [ch_str],
                "limit": 1,
                "order[chapter]": "asc",
                "contentRating[]": ["safe", "suggestive", "erotica"],
            },
        )
        chapters = data.get("data", [])
        if chapters:
            return chapters[0].get("id")
        return None

    def _get_series_title(self, manga_id: str) -> str:
        """Quick fetch of just the manga title."""
        try:
            detail = self.detail(manga_id)  # uses cache
            return detail.get("series", {}).get("title", "Unknown")
        except Exception:
            return "Unknown"

    @staticmethod
    def _extract_title(attrs: dict[str, Any]) -> str:
        """Extract the best English title from manga attributes."""
        title_map = attrs.get("title", {})
        # Try English first, then Japanese romanized, then first available
        title = title_map.get("en") or title_map.get("ja-ro", "")
        if not title:
            alt_titles = attrs.get("altTitles", [])
            for alt in alt_titles:
                if "en" in alt:
                    title = alt["en"]
                    break
        return title or "Unknown Title"

    @staticmethod
    def _extract_cover_url(manga: dict[str, Any]) -> str | None:
        """Extract cover image URL from relationships."""
        manga_id = manga.get("id", "")
        for rel in manga.get("relationships", []):
            if rel.get("type") == "cover_art":
                filename = rel.get("attributes", {}).get("fileName")
                if filename:
                    return f"{_COVER_BASE}/{manga_id}/{filename}.256.jpg"
        return None

    @staticmethod
    def _parse_chapter_number(value: Any) -> float | None:
        """Safely convert a chapter number value to float, returning None for empty/invalid."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _days_ago(n: int) -> str:
        """Return an ISO date string for *n* days ago (MangaDex format)."""
        import datetime

        dt = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=n)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")


# Set auto-discovery marker
SPIDER_CLASS = MangaDexSpider
