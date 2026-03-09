"""Comic Crawler — adaptive web scraping for comics, built on Scrapling."""

from __future__ import annotations

__version__ = "0.1.0"

# Public API — re-export the most commonly used classes
from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import (
    BlockedError,
    ComicCrawlerError,
    ConfigError,
    FetchError,
    ParseError,
    StorageError,
)
from comic_crawler.fetcher import FetcherType, create_fetcher, create_session
from comic_crawler.models import Chapter, ComicSeries, Page
from comic_crawler.pipelines import (
    DeduplicationPipeline,
    ExportPipeline,
    PipelineManager,
    ValidationPipeline,
)
from comic_crawler.storage import LocalStorage, build_image_path, create_storage

__all__ = [
    # Version
    "__version__",
    # Config
    "CrawlerConfig",
    # Models
    "ComicSeries",
    "Chapter",
    "Page",
    # Exceptions
    "ComicCrawlerError",
    "FetchError",
    "ParseError",
    "StorageError",
    "ConfigError",
    "BlockedError",
    # Fetcher
    "FetcherType",
    "create_fetcher",
    "create_session",
    # Pipelines
    "ValidationPipeline",
    "DeduplicationPipeline",
    "ExportPipeline",
    "PipelineManager",
    # Storage
    "LocalStorage",
    "build_image_path",
    "create_storage",
]
