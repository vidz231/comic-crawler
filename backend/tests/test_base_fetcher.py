"""Regression tests for BaseFetcher browser fallbacks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import FetchError
from comic_crawler.logging import get_logger
from comic_crawler.spiders.base_fetcher import BaseFetcher


class _DummyBrowserFetcher(BaseFetcher):
    """Minimal fetcher for exercising browser fetch logic."""

    def __init__(self) -> None:
        self._config = CrawlerConfig(max_retries=1)
        self._log = get_logger("test.base_fetcher")


def test_do_fetch_falls_back_on_persistent_context_crash() -> None:
    """Use the non-persistent browser path when Chromium crashes on launch."""
    fetcher = _DummyBrowserFetcher()
    expected_response = MagicMock()
    crash = RuntimeError(
        "BrowserType.launch_persistent_context: Target page, context or browser "
        "has been closed\nchrome_crashpad_handler: --database is required"
    )

    with (
        patch(
            "comic_crawler.spiders.base_fetcher.StealthyFetcher.fetch",
            side_effect=crash,
        ),
        patch.object(
            fetcher,
            "_fetch_with_ephemeral_browser",
            return_value=expected_response,
        ) as fallback,
    ):
        result = fetcher._do_fetch(
            "https://asuracomic.net/series?page=1",
            network_idle=False,
            wait_selector="a[href*='/series/']",
            block_images=True,
        )

    assert result is expected_response
    fallback.assert_called_once_with(
        "https://asuracomic.net/series?page=1",
        network_idle=False,
        wait_selector="a[href*='/series/']",
        block_images=True,
        disable_resources=True,
        timeout_ms=60000,
        proxy=None,
    )


def test_do_fetch_raises_fetch_error_for_non_fallback_failures() -> None:
    """Unexpected browser errors should still fail the request."""
    fetcher = _DummyBrowserFetcher()

    with (
        patch(
            "comic_crawler.spiders.base_fetcher.StealthyFetcher.fetch",
            side_effect=RuntimeError("browser exploded"),
        ),
        pytest.raises(FetchError, match="browser exploded"),
    ):
        fetcher._do_fetch(
            "https://example.com",
            network_idle=True,
            wait_selector=None,
            block_images=False,
        )


def test_ephemeral_fallback_raises_when_wait_selector_never_attaches() -> None:
    """Selector wait failures in ephemeral mode must propagate for retry/error handling."""
    fetcher = _DummyBrowserFetcher()

    mock_page = MagicMock()
    mock_page.locator.return_value.first.wait_for.side_effect = TimeoutError("selector timeout")

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    with (
        patch("playwright.sync_api.sync_playwright") as sync_playwright,
        patch("scrapling.engines.toolbelt.fingerprints.generate_headers", return_value={"User-Agent": "ua"}),
    ):
        sync_playwright.return_value.__enter__.return_value = mock_playwright

        with pytest.raises(TimeoutError, match="selector timeout"):
            fetcher._fetch_with_ephemeral_browser(
                "https://example.com",
                network_idle=False,
                wait_selector=".required-element",
                block_images=False,
                disable_resources=True,
                timeout_ms=5000,
                proxy=None,
            )

    mock_context.close.assert_called_once()
    mock_browser.close.assert_called_once()
