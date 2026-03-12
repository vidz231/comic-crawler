"""BaseFetcher — shared smart-fetch mixin for all comic source spiders.

Two fetch strategies are available:

**Browser strategy** (default — ``_USE_HTTP_FETCH = False``)
  Uses :class:`scrapling.fetchers.StealthyFetcher` (Playwright + stealth JS).
  Required for sites that render content with JavaScript (e.g. Asura).

  Public methods:

  - ``_fetch``         : safe fallback using ``network_idle``.
  - ``_fetch_chapter`` : fast path — waits for :attr:`_CHAPTER_SELECTOR`.
  - ``_fetch_series``  : fast path — waits for :attr:`_SERIES_SELECTOR`.
  - ``_fetch_listing`` : fast path — waits for :attr:`_LISTING_SELECTOR`.

**HTTP strategy** (``_USE_HTTP_FETCH = True``)
  Uses :class:`scrapling.fetchers.Fetcher` (``curl_cffi`` — no browser).
  Ideal for sites that serve plain HTML without JavaScript (e.g. TruyenVN).

  - ``_fetch``     : dispatches to ``_fetch_http`` automatically.
  - ``_fetch_http``: always uses the plain HTTP client.
  - The ``_fetch_chapter`` / ``_fetch_series`` / ``_fetch_listing`` fast-path
    selectors are **ignored** when HTTP mode is active (no browser = no DOM
    waiting); the response is returned immediately.

**How to add a new spider**::

    class MySpider(BaseFetcher):
        name = "mysite"
        base_url = "https://mysite.com"

        # Set True for plain-HTML sites (Madara WP, etc.).
        _USE_HTTP_FETCH = False

        # Only needed when USE_HTTP_FETCH is False.
        _CHAPTER_SELECTOR  = "img[src*='cdn.mysite.com']"
        _SERIES_SELECTOR   = "a[href*='/chapter/']"
        _LISTING_SELECTOR  = "a[href*='/manga/']"
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from scrapling.fetchers import Fetcher, StealthyFetcher

from comic_crawler.exceptions import BlockedError, FetchError
from comic_crawler.logging import get_logger

_PERSISTENT_CONTEXT_CRASH_MARKERS = (
    "BrowserType.launch_persistent_context",
    "chrome_crashpad_handler",
    "--database is required",
)


def _retry_with_backoff(
    fn: Callable[[], Any],
    *,
    max_retries: int,
    logger: Any,
    url: str,
    label: str,
) -> Any:
    """Execute *fn* with exponential back-off retry.

    Args:
        fn: Zero-argument callable to execute on each attempt.
        max_retries: Maximum number of attempts (≥1).
        logger: Structured logger for warnings.
        url: URL being fetched (for log context).
        label: Log event prefix (e.g. ``"fetch_http"`` or ``"fetch"``).

    Returns:
        The return value of *fn* on the first successful call.

    Raises:
        FetchError: After all retry attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = fn()
            if result is None:
                raise FetchError(f"{label} returned None", url=url)
            logger.debug(f"{label}_ok", url=url, attempt=attempt)
            return result
        except FetchError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                sleep_s = (2**attempt) + random.uniform(0.5, 2.0)
                logger.warning(
                    f"{label}_retry",
                    url=url,
                    attempt=attempt,
                    next_retry_in=round(sleep_s, 1),
                    error=str(exc),
                )
                time.sleep(sleep_s)

    assert last_exc is not None
    raise FetchError(
        f"{label} failed after {max_retries} attempts: {last_exc}",
        url=url,
    ) from last_exc


class BaseFetcher:
    """Mixin that provides optimised, selector-aware fetch calls.

    Subclasses declare three class-level CSS selector strings (or ``None``) to
    control when each fetch is considered "done".

    Class attributes
    ----------------
    _CHAPTER_SELECTOR : str | None
        CSS selector that becomes visible once the chapter *image URLs* are
        rendered.
    _SERIES_SELECTOR : str | None
        CSS selector that becomes visible once the series *chapter list* has
        rendered.
    _LISTING_SELECTOR : str | None
        CSS selector that becomes visible once the browse/search *series cards*
        have rendered.
    """

    # Subclasses override these.
    _USE_HTTP_FETCH: bool = False
    _CHAPTER_SELECTOR: str | None = None
    _SERIES_SELECTOR: str | None = None
    _LISTING_SELECTOR: str | None = None

    # ------------------------------------------------------------------
    # Public fast-path methods
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> Any:
        """Fetch a page — dispatches to HTTP or browser strategy."""
        if self._USE_HTTP_FETCH:
            return self._fetch_http(url)
        return self._do_fetch(
            url,
            network_idle=True,
            wait_selector=None,
            block_images=True,
        )

    def _fetch_http(self, url: str) -> Any:
        """Fetch a plain-HTML page using ``curl_cffi`` — no browser.

        Raises:
            FetchError: After all retry attempts are exhausted.
        """
        log = getattr(self, "_log", get_logger("base_fetcher"))
        config = getattr(self, "_config", None)
        max_retries = max(1, config.max_retries) if config else 1
        log.info("fetching_http", url=url)

        proxy_kwargs: dict[str, Any] = {}
        if config and config.proxy_list:
            proxy_kwargs["proxy"] = random.choice(config.proxy_list)

        def _do_request() -> Any:
            response = Fetcher.get(
                url,
                stealthy_headers=True,
                follow_redirects=True,
                timeout=30,
                **proxy_kwargs,
            )
            if response is not None:
                resp_status = getattr(response, "status", None)
                if resp_status and resp_status >= 400:
                    if resp_status == 403:
                        raise BlockedError(
                            "Blocked (HTTP 403) — likely Cloudflare",
                            url=url,
                            status_code=resp_status,
                        )
                    raise FetchError(
                        f"HTTP {resp_status} error",
                        url=url,
                        status_code=resp_status,
                    )
            return response

        return _retry_with_backoff(
            _do_request,
            max_retries=max_retries,
            logger=log,
            url=url,
            label="fetch_http",
        )

    def _fetch_chapter(self, url: str) -> Any:
        """Fetch a chapter reader page optimised for speed."""
        if self._USE_HTTP_FETCH:
            return self._fetch_http(url)
        return self._fast_fetch(
            url,
            selector=self._CHAPTER_SELECTOR,
            block_images=False,
            fallback_label="chapter_fast_fetch_failed_fallback",
        )

    def _fetch_series(self, url: str) -> Any:
        """Fetch a series detail page optimised for speed."""
        if self._USE_HTTP_FETCH:
            return self._fetch_http(url)
        return self._fast_fetch(
            url,
            selector=self._SERIES_SELECTOR,
            block_images=True,
            fallback_label="series_fast_fetch_failed_fallback",
        )

    def _fetch_listing(self, url: str) -> Any:
        """Fetch a browse/search listing page optimised for speed."""
        if self._USE_HTTP_FETCH:
            return self._fetch_http(url)
        return self._fast_fetch(
            url,
            selector=self._LISTING_SELECTOR,
            block_images=True,
            fallback_label="listing_fast_fetch_failed_fallback",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fast_fetch(
        self,
        url: str,
        *,
        selector: str | None,
        block_images: bool,
        fallback_label: str,
    ) -> Any:
        """Try a ``wait_selector`` fetch; fall back to ``network_idle``."""
        if selector is None:
            return self._fetch(url)
        try:
            return self._do_fetch(
                url,
                network_idle=False,
                wait_selector=selector,
                block_images=block_images,
            )
        except FetchError:
            log = getattr(self, "_log", get_logger("base_fetcher"))
            log.warning(fallback_label, url=url)
            return self._fetch(url)

    def _do_fetch(
        self,
        url: str,
        *,
        network_idle: bool,
        wait_selector: str | None,
        block_images: bool,
    ) -> Any:
        """Core ``StealthyFetcher`` wrapper with retry + back-off.

        Raises:
            FetchError: After all retry attempts are exhausted.
        """
        log = getattr(self, "_log", get_logger("base_fetcher"))
        config = getattr(self, "_config", None)
        max_retries = max(1, config.max_retries) if config else 1
        log.info("fetching", url=url)

        proxy_kwargs: dict[str, Any] = {}
        if config and config.proxy_list:
            proxy_kwargs["proxy"] = random.choice(config.proxy_list)

        fetch_kwargs: dict[str, Any] = {
            "headless": True,
            "network_idle": network_idle,
            "block_images": block_images,
            "disable_resources": True,
            "timeout": 60000,
            **proxy_kwargs,
        }
        if wait_selector:
            fetch_kwargs["wait_selector"] = wait_selector

        def _do_request() -> Any:
            try:
                return StealthyFetcher.fetch(url, **fetch_kwargs)
            except Exception as exc:
                if self._should_use_ephemeral_browser_fallback(exc):
                    log.warning(
                        "persistent_context_launch_failed_fallback",
                        url=url,
                        error=str(exc),
                    )
                    return self._fetch_with_ephemeral_browser(
                        url,
                        network_idle=network_idle,
                        wait_selector=wait_selector,
                        block_images=block_images,
                        disable_resources=True,
                        timeout_ms=int(fetch_kwargs["timeout"]),
                        proxy=proxy_kwargs.get("proxy"),
                    )
                raise

        return _retry_with_backoff(
            _do_request,
            max_retries=max_retries,
            logger=log,
            url=url,
            label="fetch",
        )

    @staticmethod
    def _should_use_ephemeral_browser_fallback(exc: Exception) -> bool:
        """Detect Playwright persistent-context launch crashes in Chromium."""
        message = str(exc)
        return all(marker in message for marker in _PERSISTENT_CONTEXT_CRASH_MARKERS)

    def _fetch_with_ephemeral_browser(
        self,
        url: str,
        *,
        network_idle: bool,
        wait_selector: str | None,
        block_images: bool,
        disable_resources: bool = True,
        timeout_ms: int,
        proxy: str | dict[str, str] | None,
        page_script: str | None = None,
    ) -> Any:
        """Fetch with a non-persistent Playwright browser context.

        This avoids Chromium crashes seen with ``launch_persistent_context`` in
        some container images while keeping the browser-based fetch path
        available for JS-rendered pages.
        """
        from playwright.sync_api import sync_playwright
        from scrapling.engines.toolbelt.fingerprints import generate_headers
        from scrapling.parser import Adaptor

        blocked_resource_types: set[str] = set()
        if disable_resources:
            blocked_resource_types.update(
                {
                    "beacon",
                    "csp_report",
                    "font",
                    "imageset",
                    "media",
                    "object",
                    "stylesheet",
                    "texttrack",
                    "websocket",
                }
            )
        if block_images:
            blocked_resource_types.add("image")

        launch_options: dict[str, Any] = {
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-setuid-sandbox",
                "--hide-scrollbars",
                "--lang=en-US",
                "--mute-audio",
                "--no-sandbox",
                "--window-position=0,0",
            ],
            "channel": "chromium",
            "headless": True,
            "ignore_default_args": ["--enable-automation"],
        }
        if proxy:
            launch_options["proxy"] = proxy if isinstance(proxy, dict) else {"server": proxy}

        context_options: dict[str, Any] = {
            "device_scale_factor": 2,
            "ignore_https_errors": True,
            "locale": "en-US",
            "screen": {"width": 1920, "height": 1080},
            "user_agent": generate_headers(browser_mode="chrome").get("User-Agent"),
            "viewport": {"width": 1920, "height": 1080},
        }

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_options)
            context = browser.new_context(**context_options)
            try:
                page = context.new_page()
                page.set_default_navigation_timeout(timeout_ms)
                page.set_default_timeout(timeout_ms)

                if blocked_resource_types:
                    def _handle_route(route: Any) -> None:
                        if route.request.resource_type in blocked_resource_types:
                            route.abort()
                        else:
                            route.continue_()

                    page.route("**/*", _handle_route)

                page.goto(url, wait_until="load")
                page.wait_for_load_state("domcontentloaded")

                if page_script:
                    page.evaluate(page_script)
                    page.wait_for_timeout(750)

                if wait_selector:
                    page.locator(wait_selector).first.wait_for(state="attached")

                if network_idle:
                    with suppress(Exception):
                        page.wait_for_load_state("networkidle", timeout=timeout_ms)

                return Adaptor(page.content(), url=page.url, auto_match=False)
            finally:
                context.close()
                browser.close()
