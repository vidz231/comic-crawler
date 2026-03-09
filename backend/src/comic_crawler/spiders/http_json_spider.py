"""HttpJsonSpider — abstract base for API-only comic sources.

Subclass this instead of ``BaseFetcher`` when the source provides a
public JSON API (e.g. MangaDex).  No HTML parsing or Playwright needed.

Usage::

    class MangaDexSpider(HttpJsonSpider):
        name = "mangadex"
        base_url = "https://mangadex.org"
        _BASE_API_URL = "https://api.mangadex.org"
"""

from __future__ import annotations

import time
from typing import Any

from curl_cffi import requests as curl_requests

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import FetchError
from comic_crawler.logging import get_logger

log = get_logger(__name__)

_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Comic-Crawler/0.1 (https://github.com/comic-crawler)",
}


class HttpJsonSpider:
    """Base class for comic sources with a JSON REST API.

    Provides ``_get_json`` and ``_post_json`` helpers with automatic
    retry, configurable delay, and proper error handling.

    Subclasses still need to implement the full ``SourceSpider`` protocol
    (``search``, ``detail``, ``read_chapter``, ``categories``, etc.).
    """

    # -- Override in subclass ------------------------------------------------
    _BASE_API_URL: str = ""
    _EXTRA_HEADERS: dict[str, str] = {}  # noqa: RUF012
    _MAX_RETRIES: int = 3
    _RETRY_BACKOFF: float = 1.0

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        self._config = config or CrawlerConfig()
        self._download_delay = self._config.download_delay
        self._session_headers = {**_DEFAULT_HEADERS, **self._EXTRA_HEADERS}

    # -- HTTP helpers -------------------------------------------------------

    def _get_json(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """GET an API endpoint and return the parsed JSON response.

        Args:
            endpoint: Path relative to ``_BASE_API_URL`` (e.g. ``/manga``).
            params: Optional query parameters.
            headers: Extra headers merged with the session defaults.

        Raises:
            FetchError: After all retry attempts are exhausted.
        """
        url = f"{self._BASE_API_URL}{endpoint}"
        merged_headers = {**self._session_headers, **(headers or {})}

        last_error: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                if attempt > 1 or self._download_delay > 0:
                    time.sleep(self._download_delay * attempt)

                resp = curl_requests.get(
                    url,
                    params=params,
                    headers=merged_headers,
                    timeout=15,
                    impersonate="chrome",
                )

                if resp.status_code == 429:
                    # Rate limited — back off harder
                    wait = self._RETRY_BACKOFF * attempt * 2
                    log.warning("rate_limited", url=url, wait=wait)
                    time.sleep(wait)
                    continue

                if resp.status_code >= 400:
                    raise FetchError(
                        f"HTTP {resp.status_code}",
                        url=url,
                        status_code=resp.status_code,
                    )

                data: dict[str, Any] = resp.json()
                return data

            except FetchError:
                raise
            except Exception as exc:
                last_error = exc
                log.warning(
                    "http_json_retry",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )

        raise FetchError(
            f"All {self._MAX_RETRIES} attempts failed: {last_error}",
            url=url,
        )

    def _post_json(
        self,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """POST JSON to an API endpoint and return the parsed response.

        Raises:
            FetchError: After all retry attempts are exhausted.
        """
        url = f"{self._BASE_API_URL}{endpoint}"
        merged_headers = {
            **self._session_headers,
            "Content-Type": "application/json",
            **(headers or {}),
        }

        last_error: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    time.sleep(self._RETRY_BACKOFF * attempt)

                resp = curl_requests.post(
                    url,
                    json=payload,
                    headers=merged_headers,
                    timeout=15,
                    impersonate="chrome",
                )

                if resp.status_code >= 400:
                    raise FetchError(
                        f"HTTP {resp.status_code}",
                        url=url,
                        status_code=resp.status_code,
                    )

                data: dict[str, Any] = resp.json()
                return data

            except FetchError:
                raise
            except Exception as exc:
                last_error = exc
                log.warning(
                    "http_json_post_retry",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )

        raise FetchError(
            f"All {self._MAX_RETRIES} POST attempts failed: {last_error}",
            url=url,
        )
