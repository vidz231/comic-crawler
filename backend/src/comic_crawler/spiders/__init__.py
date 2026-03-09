"""Site-specific spider implementations."""

from __future__ import annotations

from comic_crawler.spiders.registry import (
    SourceSpider,
    SpiderRegistry,
    create_default_registry,
)

__all__ = [
    "SourceSpider",
    "SpiderRegistry",
    "create_default_registry",
]
