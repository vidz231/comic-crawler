"""MangaKakalot / Manganato spider — server-rendered HTML scraping.

Scrapes manga data from mangakakalot.gg and manganato.gg using
plain HTTP fetch (``curl_cffi`` impersonation, no Playwright needed).

These sister sites share an identical DOM structure.  The spider handles
both URL patterns transparently.

.. note::

   The original domains (mangakakalot.com, chapmanganato.to) went offline
   in early 2025.  This module now targets the replacement ``.gg`` domains.
"""

from __future__ import annotations

import contextlib
import re
import time
from typing import Any

from cachetools import TTLCache
from curl_cffi import requests as curl_requests

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger
from comic_crawler.spiders.base_fetcher import BaseFetcher
from comic_crawler.spiders.mangakakalot_parser import (
    MANGAKAKALOT_BASE,
    MangaKakalotPageParser,
)

log = get_logger(__name__)

# Auto-discovery marker
SPIDER_CLASS: type | None = None  # set at module bottom

# ---------------------------------------------------------------------------
# Genre list (hardcoded — the new .gg site uses slug-based genre URLs)
# ---------------------------------------------------------------------------

_GENRES: list[dict[str, str]] = [
    {"name": "Action", "slug": "action"},
    {"name": "Adventure", "slug": "adventure"},
    {"name": "Comedy", "slug": "comedy"},
    {"name": "Drama", "slug": "drama"},
    {"name": "Fantasy", "slug": "fantasy"},
    {"name": "Harem", "slug": "harem"},
    {"name": "Historical", "slug": "historical"},
    {"name": "Horror", "slug": "horror"},
    {"name": "Isekai", "slug": "isekai"},
    {"name": "Josei", "slug": "josei"},
    {"name": "Martial Arts", "slug": "martial-arts"},
    {"name": "Mature", "slug": "mature"},
    {"name": "Mystery", "slug": "mystery"},
    {"name": "One Shot", "slug": "one-shot"},
    {"name": "Psychological", "slug": "psychological"},
    {"name": "Romance", "slug": "romance"},
    {"name": "School Life", "slug": "school-life"},
    {"name": "Sci Fi", "slug": "sci-fi"},
    {"name": "Seinen", "slug": "seinen"},
    {"name": "Shoujo", "slug": "shoujo"},
    {"name": "Shounen", "slug": "shounen"},
    {"name": "Slice of Life", "slug": "slice-of-life"},
    {"name": "Sports", "slug": "sports"},
    {"name": "Supernatural", "slug": "supernatural"},
    {"name": "Tragedy", "slug": "tragedy"},
]


# ---------------------------------------------------------------------------
# MangaKakalotSpider
# ---------------------------------------------------------------------------


class MangaKakalotSpider(BaseFetcher):
    """Concrete spider for MangaKakalot / Manganato (.gg domains).

    Uses ``BaseFetcher._fetch_http`` (``_USE_HTTP_FETCH = True``) for
    all requests — the sites are fully server-rendered.

    Implements the ``SourceSpider`` protocol for the spider registry.
    """

    # SourceSpider protocol properties
    name = "mangakakalot"
    base_url = MANGAKAKALOT_BASE

    # Manganato.gg is server-rendered — use fast HTTP fetch (no browser needed)
    _USE_HTTP_FETCH = True

    # CSS selectors (kept for documentation; ignored in HTTP mode)
    _CHAPTER_SELECTOR = ".container-chapter-reader img"
    _SERIES_SELECTOR = ".chapter-list .row a"
    _LISTING_SELECTOR = ".list-comic-item-wrap"

    # Trending periods
    trending_periods: list[str] = ["today", "weekly", "monthly", "all"]  # noqa: RUF012

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        self._config = config or CrawlerConfig()
        self._log = get_logger(f"spider.{self.name}")
        self._parser = MangaKakalotPageParser()

        # Apply per-source rate limit
        src_limits = self._config.source_rate_limits
        if "mangakakalot" in src_limits:
            self._download_delay = src_limits["mangakakalot"]

        # In-memory caches
        self._detail_cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=100, ttl=600
        )
        self._chapter_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(
            maxsize=200, ttl=1800
        )

    # -- SourceSpider protocol ---------------------------------------------

    @property
    def supports_multi_genre(self) -> bool:
        return False

    def categories(self) -> list[dict[str, str]]:
        """Return hardcoded genre list."""
        return _GENRES

    def search(
        self,
        *,
        name: str | None = None,
        page: int = 1,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Search by name via StealthyFetcher browser, or browse by genre via HTTP.

        Name search uses the HTML search page at ``/search/story/{query}``
        fetched with ``StealthyFetcher`` (Playwright with stealth) to
        bypass Cloudflare protection.

        Genre browsing uses fast HTTP fetch (plain ``curl_cffi``).
        """
        if name:
            return self._search_browser(name, page)

        # Genre / browse — fetch HTML listing page (no Cloudflare on these)
        if genre:
            url = f"{MANGAKAKALOT_BASE}/genre/{genre}?page={page}"
        else:
            url = f"{MANGAKAKALOT_BASE}/genre/all?page={page}"

        self._log.info("search", url=url)
        response = self._fetch_listing(url)

        results = self._parser.extract_search_cards(response, base_url=MANGAKAKALOT_BASE)
        has_next = self._parser.extract_has_next_page(response)

        return {
            "results": results,
            "page": page,
            "has_next_page": has_next,
            "series_count": len(results),
        }

    def _search_browser(self, name: str, page: int = 1) -> dict[str, Any]:
        """Search for manga by name, with nodriver fallback.

        Strategy:
        1. Try the direct JSON search API (``POST /home/search/json``) first.
           This bypasses Cloudflare entirely and is the fastest path.
        2. If the API fails (e.g. CF blocks with 403), fall back to
           nodriver (Chrome CDP) which bypasses CF managed challenges.
        """
        # (1) Try direct JSON API search first
        try:
            result = self._search_json_api(name, page)
            if result["results"]:
                return result
        except Exception:
            self._log.warning("search_json_api_failed", name=name, exc_info=True)

        # (2) Fall back to nodriver browser fetch
        self._log.info("search_browser_fallback", name=name, page=page)
        return self._search_with_nodriver(name, page)

    def _search_json_api(self, name: str, page: int = 1) -> dict[str, Any]:
        """Search via the site's JSON API (``POST /home/search/json``).

        This endpoint is not protected by Cloudflare Turnstile and returns
        results directly as JSON, making it the preferred search method.
        """
        search_url = f"{MANGAKAKALOT_BASE}/home/search/json"
        self._log.info("search_json_api", url=search_url, query=name)

        resp = curl_requests.post(
            search_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Referer": MANGAKAKALOT_BASE,
            },
            data={"searchword": name},
            timeout=15,
            impersonate="chrome",
        )
        if resp.status_code >= 400:
            msg = f"Search API HTTP {resp.status_code}"
            raise RuntimeError(msg)

        data = resp.json()
        if not isinstance(data, list):
            data = data.get("data", [])

        results: list[dict[str, Any]] = []
        for item in data:
            story_name = item.get("name", "")
            slug = item.get("nameunsigned", "")
            image = item.get("image", "")
            author = item.get("author", "")
            last_chapter = item.get("lastchapter", "")

            # Parse latest chapter number from string like "Chapter 100"
            latest_num = 0.0
            if last_chapter:
                ch_match = re.search(r"[\d.]+", last_chapter)
                if ch_match:
                    with contextlib.suppress(ValueError):
                        latest_num = float(ch_match.group())

            results.append({
                "title": story_name,
                "slug": slug,
                "url": f"{MANGAKAKALOT_BASE}/manga/{slug}",
                "cover_url": image,
                "author": author,
                "latest_chapter": latest_num,
                "source": self.name,
            })

        return {
            "results": results,
            "page": page,
            "has_next_page": False,  # JSON API doesn't paginate
            "series_count": len(results),
        }

    def _search_with_nodriver(self, name: str, page: int = 1) -> dict[str, Any]:
        """Fallback search using nodriver (Chrome CDP).

        Uses Chrome via DevTools Protocol to bypass Cloudflare's managed
        challenge.  The Turnstile checkbox lives inside a *closed* Shadow DOM
        that regular JS can't reach — we pierce it with
        ``CDP DOM.getDocument(pierce=True)`` and click the checkbox via
        ``CDP Input.dispatchMouseEvent`` at the exact pixel coordinates.
        """
        import asyncio

        encoded_name = re.sub(r"[^a-zA-Z0-9]", "_", name.lower()).strip("_")
        encoded_name = re.sub(r"_+", "_", encoded_name)
        url = f"{MANGAKAKALOT_BASE}/search/story/{encoded_name}"
        if page > 1:
            url += f"?page={page}"

        self._log.info("search_with_nodriver", url=url)

        html = asyncio.run(self._nodriver_fetch(url))

        # Wrap raw HTML in Scrapling Selector so parser's .css() works
        from scrapling import Selector
        response = Selector(html)

        results = self._parser.extract_search_cards(response, base_url=MANGAKAKALOT_BASE)
        has_next = self._parser.extract_has_next_page(response)

        return {
            "results": results,
            "page": page,
            "has_next_page": has_next,
            "series_count": len(results),
        }

    @staticmethod
    async def _nodriver_fetch(url: str, timeout: int = 45) -> str:
        """Fetch a CF-protected URL using nodriver, solving the managed challenge.

        Algorithm:
        1. Launch Chrome via CDP (nodriver avoids WebDriver detection).
        2. Navigate to the URL.
        3. If the CF "Just a moment..." challenge appears:
           a. Use ``DOM.getDocument(pierce=True)`` to find the Turnstile
              iframe inside the closed Shadow DOM.
           b. Get its pixel coordinates via ``DOM.getContentQuads``.
           c. Click the checkbox with ``Input.dispatchMouseEvent``.
        4. Wait for the challenge to resolve and return the page HTML.

        Returns the fully-rendered page HTML.
        """
        import asyncio
        import glob
        import os
        import shutil
        import subprocess

        import nodriver as uc
        from nodriver import cdp

        # Auto-detect Chrome/Chromium binary (playwright's install path in Docker)
        chrome_path = None
        pw_bins = glob.glob("/opt/playwright-browsers/*/chrome-linux/chrome")
        if pw_bins:
            chrome_path = pw_bins[0]

        # Start Xvfb virtual display if available (Docker) — CF detects headless
        xvfb_proc = None
        if shutil.which("Xvfb"):
            display = ":99"
            xvfb_proc = subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1280x720x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.environ["DISPLAY"] = display
            await asyncio.sleep(0.5)  # Let Xvfb start

        try:
            # Run headed (not headless) when Xvfb provides a display
            use_headless = xvfb_proc is None and not os.environ.get("DISPLAY")
            browser = await uc.start(
                headless=use_headless,
                browser_executable_path=chrome_path,
                sandbox=False,
            )
            try:
                page = await browser.get(url)
                await asyncio.sleep(3)

                for _ in range(12):  # ~60s max
                    # Check if challenge is resolved
                    try:
                        title = await page.evaluate("document.title")
                        if title and "Just a moment" not in title:
                            await asyncio.sleep(1)
                            return await page.evaluate(
                                "document.documentElement.outerHTML"
                            )
                    except Exception:
                        pass

                    # Pierce shadow DOM to find CF Turnstile iframe
                    try:
                        doc = await page.send(
                            cdp.dom.get_document(depth=-1, pierce=True)
                        )

                        def _find_cf(node):
                            if node.node_name and node.node_name.lower() == "iframe":
                                attrs = (
                                    dict(zip(node.attributes[::2], node.attributes[1::2]))
                                    if node.attributes
                                    else {}
                                )
                                if "challenges.cloudflare" in attrs.get("src", ""):
                                    return node
                            for children in (node.children, node.shadow_roots):
                                if children:
                                    for c in children:
                                        hit = _find_cf(c)
                                        if hit:
                                            return hit
                            if node.content_document:
                                hit = _find_cf(node.content_document)
                                if hit:
                                    return hit
                            return None

                        cf_node = _find_cf(doc)
                        if cf_node:
                            quads = await page.send(
                                cdp.dom.get_content_quads(node_id=cf_node.node_id)
                            )
                            if quads:
                                q = quads[0]
                                cx, cy = q[0] + 35, q[1] + 22
                                await page.send(
                                    cdp.input_.dispatch_mouse_event(
                                        "mouseMoved", x=cx, y=cy
                                    )
                                )
                                await asyncio.sleep(0.1)
                                await page.send(
                                    cdp.input_.dispatch_mouse_event(
                                        "mousePressed",
                                        x=cx,
                                        y=cy,
                                        button=cdp.input_.MouseButton("left"),
                                        click_count=1,
                                    )
                                )
                                await asyncio.sleep(0.05)
                                await page.send(
                                    cdp.input_.dispatch_mouse_event(
                                        "mouseReleased",
                                        x=cx,
                                        y=cy,
                                        button=cdp.input_.MouseButton("left"),
                                        click_count=1,
                                    )
                                )
                    except Exception:
                        pass

                    await asyncio.sleep(5)

                # Timeout — return whatever we have
                return await page.evaluate("document.documentElement.outerHTML")
            finally:
                browser.stop()
        finally:
            if xvfb_proc:
                xvfb_proc.terminate()
                xvfb_proc.wait()

    def detail(self, slug: str) -> dict[str, Any]:
        """Full series detail — fetch and parse the series page.

        The chapter list is fetched via the site's JSON API at
        ``/api/manga/{slug}/chapters`` because the HTML page loads
        chapters dynamically via JavaScript.
        """
        if slug in self._detail_cache:
            return self._detail_cache[slug]

        url = self._slug_to_url(slug)
        self._log.info("detail", url=url)
        response = self._fetch_series(url)

        title = self._parser.extract_series_title(response)
        synopsis = self._parser.extract_synopsis(response)
        cover_url = self._parser.extract_cover_url(response)
        author = self._parser.extract_author(response)
        genres = self._parser.extract_genres(response)
        status = self._parser.extract_status(response)

        series_data: dict[str, Any] = {
            "title": title,
            "url": url,
            "cover_url": cover_url,
            "synopsis": synopsis,
            "author": author,
            "genres": genres,
            "status": status,
        }

        # Fetch chapter list via JSON API (HTML loads chapters via JS)
        chapters = self._fetch_chapters_api(slug, title)

        result: dict[str, Any] = {
            "series": series_data,
            "chapters": chapters,
        }
        self._detail_cache[slug] = result
        return result

    def _fetch_chapters_api(
        self,
        slug: str,
        series_title: str,
    ) -> list[dict[str, Any]]:
        """Fetch all chapters via the site's JSON API.

        The manganato.gg site loads chapters dynamically via JavaScript,
        so the HTML page only contains ``"Loading chapters..."``.  The
        JSON API at ``/api/manga/{slug}/chapters`` returns paginated
        chapter data reliably.
        """
        all_chapters: list[dict[str, Any]] = []
        offset = 0
        limit = 100  # max chapters per page

        while True:
            api_url = (
                f"{MANGAKAKALOT_BASE}/api/manga/{slug}"
                f"/chapters?limit={limit}&offset={offset}"
            )
            self._log.info("fetch_chapters_api", url=api_url, offset=offset)

            try:
                resp = curl_requests.get(
                    api_url,
                    headers={
                        "Accept": "application/json",
                        "Referer": f"{MANGAKAKALOT_BASE}/manga/{slug}",
                    },
                    timeout=15,
                    impersonate="chrome",
                )
                if resp.status_code >= 400:
                    self._log.warning(
                        "chapters_api_http_error",
                        status=resp.status_code,
                        url=api_url,
                    )
                    break

                data = resp.json()
            except Exception:
                self._log.warning("chapters_api_error", url=api_url, exc_info=True)
                break

            if not data.get("success"):
                self._log.warning("chapters_api_not_success", url=api_url)
                break

            chapters_data = data.get("data", {}).get("chapters", [])
            if not chapters_data:
                break

            for ch in chapters_data:
                ch_num = ch.get("chapter_num", 0)
                number = float(ch_num) if ch_num else 0.0
                ch_slug = ch.get("chapter_slug", "")
                ch_name = ch.get("chapter_name", f"Chapter {number}")
                date_str = ch.get("updated_at")

                ch_url = f"{MANGAKAKALOT_BASE}/manga/{slug}/{ch_slug}"

                all_chapters.append({
                    "series_title": series_title,
                    "number": number,
                    "title": ch_name,
                    "url": ch_url,
                    "date_published": date_str,
                    "page_count": None,
                })

            pagination = data.get("data", {}).get("pagination", {})
            if not pagination.get("has_more", False):
                break

            offset += limit
            time.sleep(0.3)  # rate limit

        return all_chapters

    def read_chapter(
        self,
        slug: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Fetch page images for a chapter."""
        cache_key = f"{slug}:{chapter_number}"
        if cache_key in self._chapter_cache:
            return self._chapter_cache[cache_key]

        # Build chapter URL
        ch_str = (
            str(int(chapter_number))
            if chapter_number == int(chapter_number)
            else str(chapter_number)
        )
        chapter_url = self._build_chapter_url(slug, ch_str)

        self._log.info("read_chapter", url=chapter_url)
        response = self._fetch_chapter(chapter_url)

        # Extract title from page
        try:
            series_title = self._parser.extract_title_from_chapter_page(response)
        except Exception:
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

    def trending(self, period: str = "today") -> list[dict[str, Any]]:
        """Fetch popular/trending manga from the site."""
        type_map = {
            "today": "day",
            "weekly": "week",
            "monthly": "month",
            "all": "",
        }
        type_val = type_map.get(period, "day")

        if type_val:
            url = f"{MANGAKAKALOT_BASE}/genre/all/{type_val}?type=topview"
        else:
            url = f"{MANGAKAKALOT_BASE}/genre/all?type=topview"

        self._log.info("trending", url=url, period=period)
        response = self._fetch_listing(url)
        cards = self._parser.extract_search_cards(response, base_url=MANGAKAKALOT_BASE)

        items: list[dict[str, Any]] = []
        for rank, card in enumerate(cards[:20], start=1):
            card["rank"] = rank
            items.append(card)

        return items

    # -- URL helpers -------------------------------------------------------

    @staticmethod
    def _slug_to_url(slug: str) -> str:
        """Convert a slug to a full detail URL.

        New .gg site uses a uniform URL pattern: /manga/{slug}
        """
        return f"{MANGAKAKALOT_BASE}/manga/{slug}"

    @staticmethod
    def _build_chapter_url(slug: str, chapter_str: str) -> str:
        """Build a chapter URL from slug + chapter number.

        New .gg site pattern: /manga/{slug}/chapter-{number}
        """
        return f"{MANGAKAKALOT_BASE}/manga/{slug}/chapter-{chapter_str}"


# Set auto-discovery marker
SPIDER_CLASS = MangaKakalotSpider
