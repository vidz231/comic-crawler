"""Search and browse pagination for TruyenQQ (truyenqqno.com).

TruyenQQ search uses an AJAX POST endpoint that returns HTML fragments.
Browse/listing uses standard paginated HTML pages.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

from scrapling.fetchers import Fetcher

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger
from comic_crawler.spiders.truyenqq_parser import (
    BASE_URL,
    SEARCH_ENDPOINT,
    TruyenQQPageParser,
    abs_url,
)


class TruyenQQSearcher:
    """Handles search/browse pagination for TruyenQQ.

    - **Search** uses the AJAX endpoint:
      ``POST /frontend/search/search`` with body ``search={q}&type=0``

    - **Browse** uses paginated listing pages:
      ``/truyen-moi-cap-nhat/trang-{N}.html``

    Holds a reference to the spider and calls ``spider._fetch_listing``
    at call time (late-bound) so that test mocks/patches propagate correctly.
    """

    def __init__(
        self,
        spider: Any,
        config: CrawlerConfig,
        parser: TruyenQQPageParser | None = None,
    ) -> None:
        self._spider = spider
        self._config = config
        self._parser = parser or TruyenQQPageParser()
        self._log = get_logger("searcher.truyenqq")

    def _fetch_listing(self, url: str) -> Any:
        """Late-bound listing fetch — calls the spider's ``_fetch_listing``."""
        return self._spider._fetch_listing(url)

    def _fetch_search(self, query: str) -> Any:
        """Fetch search results via the AJAX POST endpoint.

        Uses ``scrapling.Fetcher.post`` directly (no proxy) since TruyenQQ
        search is an AJAX endpoint that returns HTML fragments.
        """
        self._log.info("fetch_search_ajax", query=query)
        response = Fetcher.post(
            SEARCH_ENDPOINT,
            data={"search": query, "type": "0"},
            headers={"X-Requested-With": "XMLHttpRequest"},
            stealthy_headers=True,
            timeout=30,
        )
        return response

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

        When a search ``name`` is provided, uses the AJAX POST endpoint.
        When a ``genre`` is provided, fetches the genre listing page.
        Otherwise, fetches the paginated latest updates listing.

        Args:
            page: Listing page number (only used for browse/genre, not search).
            name: Optional search query.
            genre: Optional genre slug to filter by category.

        Returns:
            Dict with ``results`` (list of card dicts), ``page``, and
            ``has_next_page``.
        """
        if name:
            # AJAX search — returns all results at once (no pagination)
            self._log.info("crawl_search_lite", page=page, name=name, mode="ajax")
            response = self._fetch_search(name)
            cards = self._parser.extract_search_results(response)

            self._log.info(
                "crawl_search_lite_complete",
                series_count=len(cards),
                page=1,
                has_next_page=False,
            )
            return {
                "results": cards,
                "page": 1,
                "has_next_page": False,
            }
        elif genre:
            # Genre listing with pagination
            from comic_crawler.spiders.truyenqq import TruyenQQSpider  # noqa: PLC0415
            genre_segment = TruyenQQSpider.GENRE_MAP.get(genre)
            if not genre_segment:
                # Unknown genre — return empty results
                return {"results": [], "page": page, "has_next_page": False}

            if page == 1:
                url = f"{BASE_URL}/the-loai/{genre_segment}.html"
            else:
                url = f"{BASE_URL}/the-loai/{genre_segment}/trang-{page}.html"

            self._log.info("crawl_search_lite", page=page, genre=genre, url=url, mode="genre")
            response = self._fetch_listing(url)

            cards = self._parser.extract_series_cards(response)

            # Detect next page via pagination links
            has_next_page = False
            all_links = response.css("a[href*='trang-']")
            for link in all_links:
                href = link.attrib.get("href", "")
                if f"trang-{page + 1}" in href:
                    has_next_page = True
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
        else:
            # Browse latest updates with pagination
            if page == 1:
                url = f"{BASE_URL}/truyen-moi-cap-nhat.html"
            else:
                url = f"{BASE_URL}/truyen-moi-cap-nhat/trang-{page}.html"

            self._log.info("crawl_search_lite", page=page, name=name, url=url, mode="browse")
            response = self._fetch_listing(url)

            cards = self._parser.extract_series_cards(response)

            # Detect next page via pagination links
            has_next_page = False
            all_links = response.css("a[href*='trang-']")
            for link in all_links:
                href = link.attrib.get("href", "")
                if f"trang-{page + 1}" in href:
                    has_next_page = True
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
