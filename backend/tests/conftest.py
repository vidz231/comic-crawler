"""Shared pytest fixtures for comic-crawler tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from comic_crawler.config import CrawlerConfig


@pytest.fixture
def sample_config(tmp_path: Path) -> CrawlerConfig:
    """CrawlerConfig with a temporary output directory."""
    return CrawlerConfig(output_dir=tmp_path / "output", log_level="DEBUG")


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """A temporary output directory that exists on disk."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def sample_html() -> str:
    """Minimal HTML for testing parsing logic."""
    return """
    <html>
    <head><title>Test Comic</title></head>
    <body>
        <div class="series" data-id="1">
            <h1>My Comic Series</h1>
            <img class="cover" src="https://example.com/cover.jpg">
            <ul class="chapters">
                <li class="chapter"><a href="/chapter/1">Chapter 1</a></li>
                <li class="chapter"><a href="/chapter/2">Chapter 2</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
