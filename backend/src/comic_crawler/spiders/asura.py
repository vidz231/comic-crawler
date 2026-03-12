"""AsuraComic.net spider — crawl series listings, metadata, and chapter images.

Thin orchestrator that delegates parsing to ``AsuraPageParser``,
search to ``AsuraSearcher``, and bulk flows to ``AsuraOrchestrator``.
Implements the ``SourceSpider`` protocol for the spider registry.
"""

from __future__ import annotations

import json
import random
import re
import time
from typing import Any
from urllib.parse import urlparse

from cachetools import TTLCache

from comic_crawler.spiders.base_fetcher import BaseFetcher

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger
from comic_crawler.pipelines import (
    DeduplicationPipeline,
    ExportPipeline,
    PipelineManager,
)
from comic_crawler.spiders.orchestrator import AsuraOrchestrator
from comic_crawler.spiders.parser import (
    AsuraPageParser,
    BASE_URL,
    CDN_DOMAIN,
    SERIES_PATH,
    # Re-export for backward compatibility (tests import these from here)
    _abs_url,
    abs_url,
    parse_asura_date,
    parse_chapter_number,
)
from comic_crawler.spiders.search import AsuraSearcher
from comic_crawler.storage import sanitize_filename

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# AsuraSpider
# ---------------------------------------------------------------------------


class AsuraSpider(BaseFetcher):
    """Concrete spider for asuracomic.net.

    Supports two crawling modes:

    - **Single series**: Provide a series URL to crawl its metadata,
      chapter list, and all page image URLs.
    - **Bulk discovery**: Paginate the ``/series`` listing to discover
      all available series, then crawl each one.

    Inherits ``_fetch``, ``_fetch_chapter``, ``_fetch_series``,
    ``_fetch_listing`` from :class:`BaseFetcher` — override the three
    class-level selectors below if the site DOM ever changes.

    Implements the ``SourceSpider`` protocol so it can be registered
    in the ``SpiderRegistry`` and served by the API.
    """

    name = "asura"
    base_url = BASE_URL

    # Map genre slug → Asura numeric genre ID.
    GENRE_MAP: dict[str, int] = {
        "action": 1, "adaptation": 2, "adult": 3, "adventure": 4,
        "another-chance": 5, "apocalypse": 6, "comedy": 7,
        "coming-soon": 8, "crazy-mc": 9, "cultivation": 10,
        "cute": 11, "demon": 12, "drama": 13, "dungeons": 14,
        "ecchi": 15, "fantasy": 16, "fight": 17, "game": 18,
        "genius": 19, "genius-mc": 20, "harem": 21, "hero": 22,
        "historical": 23, "isekai": 24, "josei": 25,
        "kool-kids": 26, "magic": 28, "martial-arts": 29,
        "mature": 30, "mecha": 31, "modern-setting": 32,
        "monsters": 33, "murim": 34, "mystery": 35,
        "necromancer": 36, "noble": 37, "overpowered": 38,
        "pets": 39, "post-apocalyptic": 40, "psychological": 41,
        "rebirth": 42, "regression": 43, "reincarnation": 44,
        "return": 45, "returned": 46, "returner": 47, "revenge": 48,
        "romance": 49, "school": 50, "school-life": 51,
        "sci-fi": 52, "seinen": 53, "shoujo": 54, "shounen": 55,
        "slice-of-life": 56, "sports": 57, "super-hero": 58,
        "superhero": 59, "supernatural": 60, "survival": 61,
        "suspense": 62, "system": 63, "thriller": 64,
        "time-travel": 65, "time-travel-future": 66, "tower": 67,
        "tragedy": 68, "transmigrating": 69, "video-game": 70,
        "video-games": 71, "villain": 72, "violence": 73,
        "virtual-game": 74, "virtual-reality": 75,
        "virtual-world": 76, "webtoon": 77, "wuxia": 78,
        "hard-working-mc": 79,
    }

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        self._config = config or CrawlerConfig()
        self._log = get_logger(f"spider.{self.name}")
        self._pipeline = self._build_pipeline()
        self._parser = AsuraPageParser()
        self._searcher = AsuraSearcher(self, self._config, self._parser)
        self._orchestrator = AsuraOrchestrator(self, self._config)

        # In-memory TTL caches — keyed by slug (or slug+chapter).
        # Series detail: 10 min TTL, 100 entries.
        # Chapter pages:  30 min TTL, 200 entries (images never change).
        self._detail_cache: TTLCache = TTLCache(maxsize=100, ttl=600)
        self._chapter_cache: TTLCache = TTLCache(maxsize=200, ttl=1800)

    # -- Pipeline setup --------------------------------------------------------

    def _build_pipeline(self) -> PipelineManager:
        """Build the item processing pipeline."""
        pm = PipelineManager()
        pm.add(DeduplicationPipeline(key="url"))
        pm.add(ExportPipeline(self._config.output_dir))
        return pm

    # -- Selector config (BaseFetcher) ----------------------------------------
    # These tell BaseFetcher._fast_fetch when to consider a page "ready".
    # Returns as soon as the selector appears — much faster than network_idle.

    # Chapter reader: first comic CDN image in DOM
    _CHAPTER_SELECTOR = "img[src*='gg.asuracomic.net']"
    # Series detail: chapter list links have rendered
    _SERIES_SELECTOR  = "a[href*='/chapter/']"
    # Browse/search listing: series card links have rendered
    _LISTING_SELECTOR = "a[href*='/series/']"

    # Homepage: hero section + headings have rendered (used by trending)
    _HOMEPAGE_SELECTOR = "h3"

    # Periods supported by trending() — router validates against this list.
    trending_periods: list[str] = ["today", "weekly", "monthly", "all"]

    # -- Parsing: Search / Browse — delegated to AsuraSearcher -----------------

    def crawl_search(
        self,
        start_page: int = 1,
        max_pages: int = 0,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate ``/series?page=N`` and extract series stubs."""
        return self._searcher.crawl_search(start_page, max_pages, name)

    def _extract_series_links(self, response: Any) -> list[dict[str, Any]]:
        """Extract series title + URL from a search/browse page."""
        return self._parser.extract_series_links(response)

    def _extract_series_cards(self, response: Any) -> list[dict[str, Any]]:
        """Extract rich card data from the search/browse listing page."""
        return self._parser.extract_series_cards(response)

    def crawl_search_lite(
        self,
        page: int = 1,
        name: str | None = None,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single listing page and extract card-level data."""
        return self._searcher.crawl_search_lite(page, name, genre=genre)

    # -- Parsing: Series Detail — delegated to AsuraPageParser -----------------

    def parse_series(self, url: str) -> dict[str, Any]:
        """Fetch a series page and extract metadata + chapter list.

        Args:
            url: Full URL to the series page.

        Returns:
            Dict with ``series`` (ComicSeries dict) and ``chapters``
            (list of Chapter dicts).
        """
        self._log.info("parse_series", url=url)
        response = self._fetch_series(url)

        title = self._parser.extract_series_title(response)
        synopsis = self._parser.extract_synopsis(response)
        cover_url = self._parser.extract_cover_url(response)

        series_data = {
            "title": title,
            "url": url,
            "cover_url": cover_url,
            "synopsis": synopsis,
            "author": self._parser.extract_labeled_field(response, "Author"),
            "artist": self._parser.extract_labeled_field(response, "Artist"),
            "genres": self._parser.extract_genres(response),
            "status": self._parser.extract_status(response),
            "type": self._parser.extract_labeled_field(response, "Type"),
            "rating": self._parser.extract_rating(response),
            "updated_on": self._parser.extract_labeled_field(response, "Updated On"),
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

    # -- Parsing: Chapter (JS-rendered) — delegated to AsuraPageParser ---------

    def parse_chapter(
        self,
        url: str,
        series_title: str,
    ) -> list[dict[str, Any]]:
        """Fetch a chapter page and extract all page image URLs.

        Args:
            url: Full URL to the chapter page.
            series_title: Title of the parent series.

        Returns:
            List of Page-shaped dicts with ``image_url`` for each page.
        """
        self._log.info("parse_chapter", url=url)

        chapter_num = parse_chapter_number(url)
        response = self._fetch_chapter(url)

        pages = self._parser.extract_page_images(response, series_title, chapter_num)

        self._log.info(
            "chapter_parsed",
            url=url,
            chapter=chapter_num,
            page_count=len(pages),
        )
        return pages

    # -- Orchestration — delegated to AsuraOrchestrator ------------------------

    def run_single(self, series_url: str) -> dict[str, Any]:
        """Crawl a single series: metadata → chapter list → all page images."""
        return self._orchestrator.run_single(series_url)

    def run_bulk(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Discover all series from the browse page, then crawl each."""
        return self._orchestrator.run_bulk(max_pages)

    def run_search(
        self,
        max_pages: int = 1,
        latest_chapters: int = 5,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Discover series and fetch metadata + latest chapters (no images)."""
        return self._orchestrator.run_search(max_pages, latest_chapters, name)

    # -- SourceSpider protocol -------------------------------------------------

    @staticmethod
    def slug_from_url(url: str) -> str:
        """Extract the series slug from an Asura URL."""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parts[0] == "series":
            return parts[1]
        raise ParseError(f"Cannot extract slug from URL: {url}", url=url)

    def categories(self) -> list[dict[str, str]]:
        """Return available genres — implements ``SourceSpider.categories``."""
        return [
            {"name": slug.replace("-", " ").title(), "slug": slug}
            for slug in self.GENRE_MAP
        ]

    @property
    def supports_multi_genre(self) -> bool:
        """Asura supports filtering by multiple genres at once."""
        return True

    def search(
        self,
        *,
        name: str | None = None,
        page: int = 1,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Paginated search — implements ``SourceSpider.search``."""
        return self.crawl_search_lite(page=page, name=name, genre=genre)

    def detail(self, slug: str) -> dict[str, Any]:
        """Full series detail — implements ``SourceSpider.detail``.

        Results are cached for 10 minutes (``_detail_cache``) so that
        rapid repeated API calls (e.g. frontend navigating between chapters
        of the same series) return instantly without a browser round-trip.
        """
        if slug in self._detail_cache:
            self._log.debug("detail_cache_hit", slug=slug)
            return self._detail_cache[slug]  # type: ignore[return-value]

        url = f"{BASE_URL}/series/{slug}"
        result = self.parse_series(url)
        self._detail_cache[slug] = result
        return result

    def read_chapter(
        self,
        slug: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Chapter page images — implements ``SourceSpider.read_chapter``.

        Results are cached for 30 minutes (``_chapter_cache``) since chapter
        image URLs are permanent and never change after publication.
        """
        cache_key = f"{slug}:{chapter_number}"
        if cache_key in self._chapter_cache:
            self._log.debug("chapter_cache_hit", slug=slug, chapter=chapter_number)
            return self._chapter_cache[cache_key]  # type: ignore[return-value]

        series_url = f"{BASE_URL}/series/{slug}"
        ch_str = str(int(chapter_number)) if chapter_number == int(chapter_number) else str(chapter_number)
        chapter_url = f"{series_url}/chapter/{ch_str}"

        # Fetch chapter page and extract title from it (Phase 3 fix)
        self._log.info("read_chapter", url=chapter_url)
        response = self._fetch_chapter(chapter_url)

        try:
            series_title = self._parser.extract_title_from_chapter_page(response)
        except ParseError:
            # Fallback: fetch the series page for the title
            self._log.warning("chapter_title_fallback", slug=slug)
            result = self.parse_series(series_url)
            series_title = result["series"]["title"]
            # Re-fetch chapter page using fast path
            response = self._fetch_chapter(chapter_url)

        chapter_num = parse_chapter_number(chapter_url)
        pages = self._parser.extract_page_images(response, series_title, chapter_num)

        self._log.info(
            "chapter_parsed",
            url=chapter_url,
            chapter=chapter_num,
            page_count=len(pages),
        )

        self._chapter_cache[cache_key] = pages
        return pages

    # -- Trending / Popular ----------------------------------------------------

    def _fetch_homepage(self) -> Any:
        """Fetch the homepage, waiting for headings to render."""
        return self._fast_fetch(
            BASE_URL,
            selector=self._HOMEPAGE_SELECTOR,
            block_images=False,
            fallback_label="homepage_fast_fetch_failed_fallback",
        )

    def _fetch_homepage_with_tab(self, tab_label: str) -> Any:
        """Fetch the homepage and click a Radix UI tab before scraping.

        Used for 'monthly' and 'all' periods whose content is hidden until the
        corresponding sidebar tab is clicked.

        Args:
            tab_label: Visible text of the tab button (e.g. "Monthly", "All").

        Returns:
            Scrapling Adaptor response after the tab content has re-rendered.
        """
        config = getattr(self, "_config", None)
        max_retries = max(1, config.max_retries) if config else 1

        import random as _random
        import time as _time

        proxy_kwargs: dict[str, Any] = {}
        if config and config.proxy_list:
            proxy_kwargs["proxy"] = _random.choice(config.proxy_list)

        script = f"""
            // Click the tab whose text matches '{tab_label}'
            const buttons = document.querySelectorAll('button[role="tab"], [data-radix-collection-item]');
            for (const btn of buttons) {{
                if (btn.textContent.trim() === '{tab_label}') {{
                    btn.click();
                    break;
                }}
            }}
        """

        from comic_crawler.exceptions import FetchError

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self._fetch_with_ephemeral_browser(
                    BASE_URL,
                    network_idle=True,
                    wait_selector=self._HOMEPAGE_SELECTOR,
                    block_images=False,
                    disable_resources=False,
                    timeout_ms=60000,
                    proxy=proxy_kwargs.get("proxy"),
                    page_script=script,
                )
                if response is None:
                    raise FetchError("Homepage tab fetch returned None", url=BASE_URL)
                self._log.debug("homepage_tab_fetched", tab=tab_label, attempt=attempt)
                return response
            except FetchError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < max_retries:
                    sleep_s = (2 ** attempt) + _random.uniform(0.5, 2.0)
                    self._log.warning(
                        "homepage_tab_fetch_retry",
                        tab=tab_label,
                        attempt=attempt,
                        next_retry_in=round(sleep_s, 1),
                        error=str(exc),
                    )
                    _time.sleep(sleep_s)

        assert last_exc is not None
        raise FetchError(
            f"Homepage tab fetch failed after {max_retries} attempts: {last_exc}",
            url=BASE_URL,
        ) from last_exc

    # Map trending periods to Asura listing sort order parameters.
    _TRENDING_ORDER: dict[str, str] = {
        "today": "update",      # Most recently updated
        "weekly": "rating",     # Top rated
        "monthly": "rating",    # Top rated (same endpoint, limited results)
        "all": "bookmarks",     # Most bookmarked (all-time popularity)
    }

    def trending(self, period: str = "today") -> list[dict[str, Any]]:
        """Fetch trending / popular comics.  Implements ``SourceSpider.trending``.

        Uses the listing page sorted by the appropriate order parameter
        rather than scraping the homepage (which renders unreliably).

        Args:
            period: One of ``trending_periods`` (``today``, ``weekly``,
                ``monthly``, ``all``).

        Returns:
            List of TrendingItem-shaped dicts.
        """
        self._log.info("trending", period=period)

        order = self._TRENDING_ORDER.get(period, "update")
        url = f"{BASE_URL}{SERIES_PATH}?page=1&order={order}"

        response = self._fetch(url)
        cards = self._parser.extract_series_cards(response)

        # Convert card dicts to TrendingItem shape
        items: list[dict[str, Any]] = []
        for i, card in enumerate(cards):
            items.append({
                "rank": i + 1,
                "title": card["title"],
                "slug": card["slug"],
                "url": card["url"],
                "cover_url": card.get("cover_url"),
                "genres": [],
                "rating": card.get("rating"),
                "latest_chapter": card.get("latest_chapter"),
                "view_count": None,
            })

        self._log.info("trending_complete", period=period, count=len(items))
        return items

    # -- Export ----------------------------------------------------------------


    def _export_results(
        self,
        series_title: str,
        data: dict[str, Any],
    ) -> None:
        """Write crawl results to a JSON file."""
        output_dir = self._config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{sanitize_filename(series_title)}.json"
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        self._log.info("results_exported", path=str(filepath))
