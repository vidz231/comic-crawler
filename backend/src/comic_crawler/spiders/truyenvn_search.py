"""Search and browse pagination for TruyenVN (Madara WP theme)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger
from comic_crawler.spiders.truyenvn_parser import (
    BASE_URL,
    TruyenVNPageParser,
    abs_url,
)


class TruyenVNSearcher:
    """Handles search/browse pagination for TruyenVN.

    Uses the Madara WP search endpoint:
    ``/?s={query}&post_type=wp-manga``

    Holds a reference to the spider and calls ``spider._fetch`` at call
    time (late-bound) so that test mocks/patches propagate correctly.
    """

    def __init__(
        self,
        spider: Any,
        config: CrawlerConfig,
        parser: TruyenVNPageParser | None = None,
    ) -> None:
        self._spider = spider
        self._config = config
        self._parser = parser or TruyenVNPageParser()
        self._log = get_logger("searcher.truyenvn")

    def _fetch(self, url: str) -> Any:
        """Late-bound listing fetch — calls the spider's ``_fetch_listing``.

        With ``_USE_HTTP_FETCH = True`` on :class:`TruyenVNSpider`, this
        transparently routes through ``curl_cffi`` (no Playwright browser).
        """
        return self._spider._fetch_listing(url)

    def _rate_limit(self) -> None:
        """Sleep for the configured download delay."""
        if self._config.download_delay > 0:
            time.sleep(self._config.download_delay)

    def crawl_search_lite(
        self,
        page: int = 1,
        name: str | None = None,
        *,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single listing page and extract card-level data.

        Uses the Madara WP search: ``/?s={name}&post_type=wp-manga``
        or genre listing: ``/the-loai/{slug}/``
        or paginated: ``/page/{N}/?s={name}&post_type=wp-manga``

        Args:
            page: Listing page number.
            name: Optional search query.
            genre: Optional genre slug to filter by category.

        Returns:
            Dict with ``results`` (list of card dicts), ``page``, and
            ``has_next_page``.
        """
        if genre:
            # Genre listing with pagination
            from comic_crawler.spiders.truyenvn import TruyenVNSpider  # noqa: PLC0415
            genre_slug = TruyenVNSpider.GENRE_MAP.get(genre)
            if not genre_slug:
                return {"results": [], "page": page, "has_next_page": False}

            if page == 1:
                url = f"{BASE_URL}/the-loai/{genre_slug}/"
            else:
                url = f"{BASE_URL}/the-loai/{genre_slug}/page/{page}/"

            self._log.info("crawl_search_lite", page=page, genre=genre, url=url)
            response = self._fetch(url)

            # Genre pages use trending card layout (div.page-item-detail)
            cards = self._parser.extract_trending_cards(response)
            # Strip rank (not meaningful for genre browse), normalize shape
            results = []
            for card in cards:
                results.append({
                    "title": card["title"],
                    "slug": card["slug"],
                    "url": card["url"],
                    "latest_chapter": card.get("latest_chapter"),
                    "cover_url": card.get("cover_url"),
                    "status": None,
                    "rating": card.get("rating"),
                })
        else:
            if page == 1:
                url = f"{BASE_URL}/?s={quote(name or '')}&post_type=wp-manga"
            else:
                url = f"{BASE_URL}/page/{page}/?s={quote(name or '')}&post_type=wp-manga"

            self._log.info("crawl_search_lite", page=page, name=name, url=url)
            response = self._fetch(url)

            results = self._parser.extract_series_cards(response)

        # Detect next page via "Older Posts" / nav-previous link
        has_next_page = False
        nav_links = response.css("div.nav-previous a")
        if not nav_links:
            nav_links = response.css("a.nextpostslink")
        if not nav_links:
            nav_links = response.css(".navigation-ajax a")
        if nav_links:
            has_next_page = True

        self._log.info(
            "crawl_search_lite_complete",
            series_count=len(results),
            page=page,
            has_next_page=has_next_page,
        )
        return {
            "results": results,
            "page": page,
            "has_next_page": has_next_page,
        }
