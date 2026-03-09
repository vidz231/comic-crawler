"""Shared FastAPI dependency callables.

Import these with ``Depends()`` inside route handlers.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from comic_crawler.config import CrawlerConfig
from comic_crawler.spiders.registry import (
    SpiderRegistry,
    SourceSpider,
    create_default_registry,
)


@lru_cache(maxsize=1)
def get_config() -> CrawlerConfig:
    """Return a cached ``CrawlerConfig`` instance.

    Reads environment variables / .env on first call and caches the result
    for the lifetime of the process.
    """
    return CrawlerConfig()


@lru_cache(maxsize=1)
def get_registry() -> SpiderRegistry:
    """Return a cached ``SpiderRegistry`` with all built-in sources.

    A single registry instance is shared across all requests.
    """
    config = get_config()
    return create_default_registry(config)


def resolve_source(
    source: str,
    registry: SpiderRegistry,
) -> SourceSpider:
    """Look up a source spider by name, raising 404 if unknown."""
    try:
        return registry.get(source)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown source: '{source}'. Use GET /api/v1/sources to list available sources.",
        )
