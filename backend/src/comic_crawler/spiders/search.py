"""Search and browse pagination for Asura — extracted from AsuraSpider."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote, urlparse, parse_qs

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger
from comic_crawler.spiders.parser import (
    AsuraPageParser,
    BASE_URL,
    SERIES_PATH,
    abs_url,
)


class AsuraSearcher:
    """Handles search/browse pagination against the Asura listing pages.

    Holds a reference to the spider and calls ``spider._fetch`` at call
    time (late-bound) so that test mocks/patches propagate correctly.
    """

    def __init__(
        self,
        spider: Any,
        config: CrawlerConfig,
        parser: AsuraPageParser | None = None,
    ) -> None:
        self._spider = spider
        self._config = config
        self._parser = parser or AsuraPageParser()
        self._log = get_logger("searcher.asura")

    def _fetch(self, url: str) -> Any:
        """Late-bound listing fetch — calls the spider's fast ``_fetch_listing``."""
        return self._spider._fetch_listing(url)

    def _rate_limit(self) -> None:
        """Sleep for the configured download delay."""
        if self._config.download_delay > 0:
            time.sleep(self._config.download_delay)

    def crawl_search(
        self,
        start_page: int = 1,
        max_pages: int = 0,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate ``/series?page=N`` and extract series stubs.

        Args:
            start_page: First page number to fetch.
            max_pages: Maximum number of pages to crawl (0 = unlimited).
            name: Optional search query to filter by series name.

        Returns:
            List of dicts with ``title`` and ``url`` for each discovered series.
        """
        discovered: list[dict[str, Any]] = []
        page = start_page
        pages_crawled = 0

        while True:
            if max_pages and pages_crawled >= max_pages:
                self._log.info("max_pages_reached", max_pages=max_pages)
                break

            url = f"{BASE_URL}{SERIES_PATH}?page={page}"
            if name:
                url += f"&name={quote(name)}"
            self._log.info("crawl_search_page", page=page, url=url)

            response = self._fetch(url)
            series_links = self._parser.extract_series_links(response)

            if not series_links:
                self._log.info("search_pagination_end", page=page)
                break

            discovered.extend(series_links)
            pages_crawled += 1
            page += 1

            self._rate_limit()

        self._log.info(
            "search_complete",
            total_series=len(discovered),
            pages_crawled=pages_crawled,
        )
        return discovered

    def crawl_search_lite(
        self,
        page: int = 1,
        name: str | None = None,
        *,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single listing page and extract card-level data.

        This is a **fast** alternative to ``crawl_search`` — it extracts
        title, latest chapter, cover, status, and rating directly from
        the listing page without visiting individual series pages.

        Args:
            page: Listing page number.
            name: Optional search query to filter by series name.
            genre: Optional genre slug to filter by category.

        Returns:
            Dict with ``results`` (list of card dicts), ``page``, and
            ``has_next_page``.
        """
        url = f"{BASE_URL}{SERIES_PATH}?page={page}"
        if name:
            url += f"&name={quote(name)}"
        if genre:
            # Resolve genre slug(s) → numeric ID(s) from AsuraSpider.GENRE_MAP
            # Supports comma-separated slugs for multi-genre (e.g. "action,fantasy")
            from comic_crawler.spiders.asura import AsuraSpider  # noqa: PLC0415
            slugs = [s.strip() for s in genre.split(",") if s.strip()]
            genre_ids = []
            for slug in slugs:
                gid = AsuraSpider.GENRE_MAP.get(slug)
                if gid:
                    genre_ids.append(str(gid))
            if genre_ids:
                url += f"&genres={','.join(genre_ids)}"

        self._log.info("crawl_search_lite", page=page, name=name, genre=genre, url=url)
        response = self._fetch(url)

        cards = self._parser.extract_series_cards(response)

        # Determine if there's a next page
        has_next_page = False
        nav_links = response.css("a[href]")
        for nav_link in nav_links:
            href = nav_link.attrib.get("href", "")
            abs_href = abs_url(href)
            parsed = urlparse(abs_href)
            qs = parse_qs(parsed.query)
            page_vals = qs.get("page", [])
            for pv in page_vals:
                try:
                    if int(pv) == page + 1:
                        has_next_page = True
                        break
                except ValueError:
                    continue
            if has_next_page:
                break

        self._log.info(
            "crawl_search_lite_complete",
            series_count=len(cards),
            page=page,
            has_next_page=has_next_page,
        )
        return {
            "results": cards,
            "page": page,
            "has_next_page": has_next_page,
        }
