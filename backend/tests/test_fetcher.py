"""Tests for the fetcher factory."""

from __future__ import annotations

import pytest

from comic_crawler.config import CrawlerConfig
from comic_crawler.fetcher import FetcherType, create_fetcher


class TestFetcherType:
    """Test FetcherType enum values."""

    def test_http_value(self) -> None:
        assert FetcherType.HTTP == "http"

    def test_stealthy_value(self) -> None:
        assert FetcherType.STEALTHY == "stealthy"

    def test_dynamic_value(self) -> None:
        assert FetcherType.DYNAMIC == "dynamic"


class TestCreateFetcher:
    """Test the create_fetcher factory function."""

    def test_returns_fetcher_for_http(self) -> None:
        from scrapling.fetchers import Fetcher

        config = CrawlerConfig()
        result = create_fetcher(config, FetcherType.HTTP)
        assert result is Fetcher

    def test_returns_stealthy_fetcher(self) -> None:
        from scrapling.fetchers import StealthyFetcher

        config = CrawlerConfig()
        result = create_fetcher(config, FetcherType.STEALTHY)
        assert result is StealthyFetcher

    def test_default_is_http(self) -> None:
        from scrapling.fetchers import Fetcher

        config = CrawlerConfig()
        result = create_fetcher(config)
        assert result is Fetcher

    def test_dynamic_fetcher_returns_class(self) -> None:
        """DynamicFetcher should be importable (requires playwright install)."""
        config = CrawlerConfig()
        try:
            result = create_fetcher(config, FetcherType.DYNAMIC)
            # If Playwright is installed, we get the class
            assert result is not None
        except ImportError:
            # Playwright not installed — that's fine for unit tests
            pytest.skip("Playwright not installed")
