"""Fetcher factory wrapping Scrapling's fetcher types."""

from __future__ import annotations

from enum import Enum
from typing import Any

from scrapling.fetchers import Fetcher, StealthyFetcher
from scrapling.engines.toolbelt.proxy_rotation import ProxyRotator

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger

log = get_logger(__name__)


class FetcherType(str, Enum):
    """Available fetcher strategies."""

    HTTP = "http"
    STEALTHY = "stealthy"
    DYNAMIC = "dynamic"


def _build_proxy_rotator(proxy_list: list[str]) -> ProxyRotator | None:
    """Create a ProxyRotator from a list of proxy URLs, or None if empty."""
    if not proxy_list:
        return None
    log.info("proxy_rotation_enabled", proxy_count=len(proxy_list))
    return ProxyRotator(proxy_list)


def create_fetcher(
    config: CrawlerConfig,
    fetcher_type: FetcherType = FetcherType.HTTP,
) -> type[Fetcher] | type[StealthyFetcher] | Any:
    """Return the appropriate Scrapling fetcher *class* for the given type.

    The caller uses the returned class to make requests, e.g.::

        fetcher_cls = create_fetcher(config, FetcherType.STEALTHY)
        page = fetcher_cls.fetch(url, headless=True)

    Args:
        config: Crawler configuration.
        fetcher_type: Which fetcher strategy to use.

    Returns:
        A Scrapling fetcher class (not an instance).
    """
    log.debug("create_fetcher", fetcher_type=fetcher_type.value)

    if fetcher_type == FetcherType.HTTP:
        return Fetcher
    elif fetcher_type == FetcherType.STEALTHY:
        return StealthyFetcher
    elif fetcher_type == FetcherType.DYNAMIC:
        # Lazy import to avoid requiring Playwright when not needed
        from scrapling.fetchers import DynamicFetcher
        return DynamicFetcher
    else:
        raise ValueError(f"Unknown fetcher type: {fetcher_type}")


def create_session(
    config: CrawlerConfig,
    fetcher_type: FetcherType = FetcherType.HTTP,
) -> Any:
    """Create a persistent session for stateful multi-request crawling.

    Sessions keep connections / browser instances alive across requests,
    which is more efficient for crawling multiple pages on the same site.

    Args:
        config: Crawler configuration.
        fetcher_type: Which fetcher strategy to use.

    Returns:
        A Scrapling session instance.
    """
    proxy_rotator = _build_proxy_rotator(config.proxy_list)
    common_kwargs: dict[str, Any] = {}

    if proxy_rotator is not None:
        common_kwargs["proxy_rotator"] = proxy_rotator

    log.debug("create_session", fetcher_type=fetcher_type.value, has_proxy=proxy_rotator is not None)

    if fetcher_type == FetcherType.HTTP:
        from scrapling.fetchers import FetcherSession
        return FetcherSession(**common_kwargs)
    elif fetcher_type == FetcherType.STEALTHY:
        from scrapling.fetchers import StealthySession
        return StealthySession(**common_kwargs)  # type: ignore[return-value]
    elif fetcher_type == FetcherType.DYNAMIC:
        from scrapling.fetchers import DynamicSession
        return DynamicSession(**common_kwargs)  # type: ignore[return-value]
    else:
        raise ValueError(f"Unknown fetcher type: {fetcher_type}")
