"""Router: browse / search across sources.

GET  /api/v1/browse   — lightweight browse from a single source.
GET  /api/v1/search   — search across one or multiple sources.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from comic_crawler.api.dependencies import get_registry, resolve_source
from comic_crawler.api.schemas import (
    MultiSearchResult,
    SearchLiteItem,
    SearchLiteResult,
)
from comic_crawler.exceptions import ComicCrawlerError
from comic_crawler.spiders.registry import SpiderRegistry

router = APIRouter()


# ---------------------------------------------------------------------------
# Browse (single source, lightweight)
# ---------------------------------------------------------------------------


@router.get(
    "/browse",
    response_model=SearchLiteResult,
    summary="Browse / search series (lightweight)",
    description=(
        "Returns series name, latest chapter, cover, status, and rating "
        "extracted directly from the listing page — no per-series page visits. "
        "Specify the source to browse."
    ),
)
async def browse_series(
    source: Annotated[str, Query(description="Source to browse (e.g. 'asura')")],
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
    name: str | None = Query(default=None, description="Filter series by title"),
    genre: str | None = Query(
        default=None, description="Filter by genre slug (e.g. 'action')"
    ),
    page: int = Query(default=1, ge=1, description="Listing page number"),
) -> SearchLiteResult:
    """Browse a source listing with optional name/genre filter."""
    spider = resolve_source(source, registry)
    try:
        raw = await asyncio.to_thread(
            spider.search, name=name, page=page, genre=genre
        )
    except ComicCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Browse failed: {exc}",
        ) from exc

    items = [SearchLiteItem(**card) for card in raw["results"]]
    return SearchLiteResult(
        source=source,
        series_count=len(items),
        page=raw["page"],
        has_next_page=raw["has_next_page"],
        results=items,
    )


# ---------------------------------------------------------------------------
# Search (multi-source) — concurrent with per-source error resilience
# ---------------------------------------------------------------------------


async def _search_single_source(
    source_name: str,
    registry: SpiderRegistry,
    *,
    name: str | None,
    genre: str | None,
    page: int,
) -> SearchLiteResult | None:
    """Search a single source, returning None on failure."""
    try:
        spider = resolve_source(source_name, registry)
    except HTTPException:
        return None

    try:
        raw: dict[str, Any] = await asyncio.to_thread(
            spider.search, name=name, page=page, genre=genre
        )
    except Exception:
        return None

    items = [SearchLiteItem(**card) for card in raw["results"]]
    return SearchLiteResult(
        source=source_name,
        series_count=len(items),
        page=raw["page"],
        has_next_page=raw["has_next_page"],
        results=items,
    )


@router.get(
    "/search",
    response_model=MultiSearchResult,
    summary="Search comics across sources",
    description=(
        "Search one or multiple sources concurrently. Pass `sources` as a "
        "comma-separated list (e.g. `sources=asura,mangadex`). If omitted, "
        "searches all registered sources."
    ),
)
async def search_comics(
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
    sources: str | None = Query(
        default=None,
        description="Comma-separated source names to search (default: all)",
    ),
    name: str | None = Query(
        default=None, description="Search query to filter by title"
    ),
    genre: str | None = Query(
        default=None, description="Filter by genre slug (e.g. 'action')"
    ),
    page: int = Query(default=1, ge=1, description="Listing page number"),
) -> MultiSearchResult:
    """Search across one or multiple comic sources concurrently."""
    # Determine which sources to query
    if sources:
        source_names = [s.strip() for s in sources.split(",") if s.strip()]
    else:
        source_names = [s["name"] for s in registry.list_sources()]

    # Search all sources concurrently
    tasks = [
        _search_single_source(
            sn, registry, name=name, genre=genre, page=page
        )
        for sn in source_names
    ]
    gathered = await asyncio.gather(*tasks)

    # Collect successful results, skip failures (None)
    per_source_results: list[SearchLiteResult] = [
        r for r in gathered if r is not None
    ]
    total_count = sum(r.series_count for r in per_source_results)

    return MultiSearchResult(
        total_count=total_count,
        sources_queried=source_names,
        results=per_source_results,
    )
