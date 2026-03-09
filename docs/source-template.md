# Adding a New Comic Source — Developer Guide

This guide walks you through adding a new comic source to comic-crawler.

## Step 1: Choose Your Base Class

| If the source has… | Use | Example |
|---------------------|-----|---------|
| A public **JSON API** | `HttpJsonSpider` | MangaDex |
| **Server-rendered HTML** (no JS needed) | `BaseFetcher` with `_USE_HTTP_FETCH = True` | MangaKakalot, TruyenVN, TruyenQQ |
| **JavaScript-rendered pages** | `BaseFetcher` with `_USE_HTTP_FETCH = False` | AsuraScans |

## Step 2: Create Your Spider Module

Create a new file at `src/comic_crawler/spiders/mysite.py`:

```python
"""MyNewSite spider — <describe the site>."""

from __future__ import annotations
from typing import Any
from cachetools import TTLCache
from comic_crawler.config import CrawlerConfig
from comic_crawler.spiders.base_fetcher import BaseFetcher  # or HttpJsonSpider

# Auto-discovery marker — the registry picks this up
SPIDER_CLASS: type | None = None  # set at module bottom


class MySiteSpider(BaseFetcher):
    """Spider for mysite.com."""

    name = "mysite"                        # unique, URL-safe
    base_url = "https://mysite.com"
    _USE_HTTP_FETCH = True                 # True for server-rendered HTML

    trending_periods: list[str] = ["today", "weekly"]

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        self._config = config or CrawlerConfig()
        self._detail_cache: TTLCache = TTLCache(maxsize=100, ttl=600)
        self._chapter_cache: TTLCache = TTLCache(maxsize=200, ttl=1800)

    @property
    def supports_multi_genre(self) -> bool:
        return False

    def categories(self) -> list[dict[str, str]]:
        return [{"name": "Action", "slug": "action"}, ...]

    def search(
        self, *, name: str | None = None, page: int = 1, genre: str | None = None
    ) -> dict[str, Any]:
        # Return: {"results": [...], "page": int, "has_next_page": bool, "series_count": int}
        ...

    def detail(self, slug: str) -> dict[str, Any]:
        # Return: {"series": {...}, "chapters": [...]}
        ...

    def read_chapter(self, slug: str, chapter_number: float) -> list[dict[str, Any]]:
        # Return: [{"series_title": str, "chapter_number": float,
        #           "page_number": int, "image_url": str}, ...]
        ...


SPIDER_CLASS = MySiteSpider  # enables auto-discovery
```

## Step 3: For HTML Sites — Create a Parser

Create `src/comic_crawler/spiders/mysite_parser.py`:

```python
class MySiteParser:
    def extract_search_cards(self, response) -> list[dict]: ...
    def extract_series_title(self, response) -> str: ...
    def extract_chapter_list(self, response, title) -> list[dict]: ...
    def extract_page_images(self, response, title, chapter_num) -> list[dict]: ...
```

## Step 4: Write Tests

Create `tests/test_mysite_spider.py`:

```python
from comic_crawler.spiders.mysite import MySiteSpider
from comic_crawler.spiders.registry import SourceSpider

def test_satisfies_protocol():
    assert isinstance(MySiteSpider(), SourceSpider)

def test_name():
    assert MySiteSpider().name == "mysite"
```

Mock HTTP responses using `unittest.mock.patch`. See `tests/test_mangadex_spider.py` for examples.

## Step 5: Verify

```bash
# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/comic_crawler/
```

## Key Rules

1. **Always implement** `name`, `base_url`, `supports_multi_genre`, `categories()`, `search()`, `detail()`, `read_chapter()`
2. **Set** `SPIDER_CLASS = YourSpider` at the end of the module for auto-discovery
3. **Use TTL caches** for `detail()` and `read_chapter()` — avoid hammering upstream sources
4. **Respect rate limits** — use `self._config.source_rate_limits.get("mysite", default)` for configurable delays
5. **Handle errors gracefully** — raise `FetchError` or `ParseError` from `comic_crawler.exceptions`
