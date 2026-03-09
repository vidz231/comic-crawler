"""Bulk orchestration flows — extracted from AsuraSpider."""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import FetchError, ParseError
from comic_crawler.logging import get_logger
from comic_crawler.storage import sanitize_filename


class _SpiderLike(Protocol):
    """Minimal interface needed by the orchestrator."""

    _config: CrawlerConfig

    def parse_series(self, url: str) -> dict[str, Any]: ...
    def parse_chapter(self, url: str, series_title: str) -> list[dict[str, Any]]: ...
    def crawl_search(self, start_page: int = 1, max_pages: int = 0, name: str | None = None) -> list[dict[str, Any]]: ...
    def _export_results(self, series_title: str, data: dict[str, Any]) -> None: ...


class AsuraOrchestrator:
    """High-level crawl orchestration — ``run_single``, ``run_bulk``, ``run_search``.

    Delegates actual fetching and parsing to the spider instance.
    """

    def __init__(self, spider: Any, config: CrawlerConfig) -> None:
        self._spider = spider
        self._config = config
        self._log = get_logger("orchestrator.asura")

    def _rate_limit(self) -> None:
        """Sleep for the configured download delay."""
        if self._config.download_delay > 0:
            time.sleep(self._config.download_delay)

    def run_single(self, series_url: str) -> dict[str, Any]:
        """Crawl a single series: metadata → chapter list → all page images.

        Args:
            series_url: Full URL to the series page.

        Returns:
            Dict with ``series``, ``chapters``, and ``pages`` keys.
        """
        self._log.info("run_single_start", url=series_url)

        # Step 1: Parse series metadata + chapter list
        result = self._spider.parse_series(series_url)
        series_data = result["series"]
        chapters = result["chapters"]

        # Step 2: Parse each chapter for page images
        all_pages: list[dict[str, Any]] = []
        for i, chapter in enumerate(chapters):
            self._log.info(
                "crawling_chapter",
                chapter=chapter["number"],
                progress=f"{i + 1}/{len(chapters)}",
            )
            try:
                pages = self._spider.parse_chapter(
                    chapter["url"],
                    series_data["title"],
                )
                all_pages.extend(pages)
            except (FetchError, ParseError) as exc:
                self._log.warning(
                    "chapter_failed",
                    chapter=chapter["number"],
                    error=str(exc),
                )

            self._rate_limit()

        # Step 3: Export results
        result_data = {
            "series": series_data,
            "chapters": chapters,
            "pages": all_pages,
        }

        self._spider._export_results(series_data["title"], result_data)

        self._log.info(
            "run_single_complete",
            title=series_data["title"],
            chapters=len(chapters),
            pages=len(all_pages),
        )
        return result_data

    def run_bulk(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Discover all series from the browse page, then crawl each.

        Args:
            max_pages: Max search pages to crawl (0 = unlimited).

        Returns:
            List of result dicts, one per series.
        """
        self._log.info("run_bulk_start", max_pages=max_pages)

        series_stubs = self._spider.crawl_search(max_pages=max_pages)
        self._log.info("bulk_discovery_complete", series_count=len(series_stubs))

        results: list[dict[str, Any]] = []
        for i, stub in enumerate(series_stubs):
            self._log.info(
                "bulk_crawling_series",
                title=stub["title"],
                progress=f"{i + 1}/{len(series_stubs)}",
            )
            try:
                result = self.run_single(stub["url"])
                results.append(result)
            except (FetchError, ParseError) as exc:
                self._log.warning(
                    "series_failed",
                    title=stub["title"],
                    error=str(exc),
                )

        self._log.info("run_bulk_complete", series_crawled=len(results))
        return results

    def run_search(
        self,
        max_pages: int = 1,
        latest_chapters: int = 5,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Discover series and fetch metadata + latest chapters (no images).

        Args:
            max_pages: Max search pages to crawl (0 = unlimited).
            latest_chapters: Number of latest chapters to keep per series.
            name: Optional search query to filter by series name.

        Returns:
            List of dicts, each with ``series`` and ``chapters`` keys.
        """
        self._log.info(
            "run_search_start",
            max_pages=max_pages,
            latest_chapters=latest_chapters,
            name=name,
        )

        series_stubs = self._spider.crawl_search(max_pages=max_pages, name=name)
        self._log.info("search_discovery_complete", series_count=len(series_stubs))

        results: list[dict[str, Any]] = []
        for i, stub in enumerate(series_stubs):
            self._log.info(
                "search_fetching_series",
                title=stub["title"],
                progress=f"{i + 1}/{len(series_stubs)}",
            )
            try:
                result = self._spider.parse_series(stub["url"])

                if latest_chapters > 0 and len(result["chapters"]) > latest_chapters:
                    result["chapters"] = result["chapters"][-latest_chapters:]

                results.append(result)
            except (FetchError, ParseError) as exc:
                self._log.warning(
                    "search_series_failed",
                    title=stub["title"],
                    error=str(exc),
                )

            self._rate_limit()

        # Export all to a single JSON file
        output_dir = self._config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / "asura_search.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        self._log.info(
            "run_search_complete",
            series_found=len(results),
            path=str(filepath),
        )
        return results
