"""Tests for CrawlerConfig."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import ConfigError


class TestCrawlerConfigDefaults:
    """Test that defaults are sensible."""

    def test_default_concurrency(self) -> None:
        config = CrawlerConfig()
        assert config.concurrency == 5

    def test_default_download_delay(self) -> None:
        config = CrawlerConfig()
        assert config.download_delay == 0.5

    def test_default_max_retries(self) -> None:
        config = CrawlerConfig()
        assert config.max_retries == 3

    def test_default_output_dir(self) -> None:
        config = CrawlerConfig()
        assert config.output_dir == Path("output")

    def test_default_log_level(self) -> None:
        config = CrawlerConfig()
        assert config.log_level == "INFO"

    def test_default_storage_backend(self) -> None:
        config = CrawlerConfig()
        assert config.storage_backend == "local"

    def test_default_proxy_list_empty(self) -> None:
        config = CrawlerConfig()
        assert config.proxy_list == []


class TestCrawlerConfigOverrides:
    """Test explicit value overrides."""

    def test_override_concurrency(self) -> None:
        config = CrawlerConfig(concurrency=10)
        assert config.concurrency == 10

    def test_override_output_dir_string(self) -> None:
        config = CrawlerConfig(output_dir="/tmp/comics")
        assert config.output_dir == Path("/tmp/comics")

    def test_override_log_level_lowercase(self) -> None:
        config = CrawlerConfig(log_level="debug")
        assert config.log_level == "DEBUG"

    def test_override_proxy_list(self) -> None:
        proxies = ["http://p1:8080", "http://p2:8080"]
        config = CrawlerConfig(proxy_list=proxies)
        assert config.proxy_list == proxies


class TestCrawlerConfigValidation:
    """Test validation rules."""

    def test_invalid_log_level_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid log_level"):
            CrawlerConfig(log_level="VERBOSE")

    def test_concurrency_must_be_positive(self) -> None:
        with pytest.raises(Exception):
            CrawlerConfig(concurrency=0)

    def test_concurrency_max_50(self) -> None:
        with pytest.raises(Exception):
            CrawlerConfig(concurrency=100)

    def test_download_delay_non_negative(self) -> None:
        with pytest.raises(Exception):
            CrawlerConfig(download_delay=-1.0)


class TestCrawlerConfigEnvVars:
    """Test environment variable loading."""

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMIC_CONCURRENCY", "20")
        monkeypatch.setenv("COMIC_LOG_LEVEL", "WARNING")
        config = CrawlerConfig()
        assert config.concurrency == 20
        assert config.log_level == "WARNING"
