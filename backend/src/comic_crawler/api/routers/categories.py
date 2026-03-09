"""Router: categories / genres for each source.

GET  /api/v1/categories  — list available genres for a source (or all sources).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from comic_crawler.api.dependencies import get_registry, resolve_source
from comic_crawler.api.schemas import CategoriesResponse, CategoryItem
from comic_crawler.spiders.registry import SpiderRegistry

router = APIRouter()


@router.get(
    "/categories",
    response_model=list[CategoriesResponse],
    summary="List available categories",
    description=(
        "Returns the list of genres/categories for one or all sources. "
        "Pass `source` to query a single source, or omit to get all."
    ),
)
async def list_categories(
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
    source: str | None = Query(
        default=None,
        description="Source name (e.g. 'asura'). Omit to list all sources.",
    ),
) -> list[CategoriesResponse]:
    """List available categories/genres per source."""
    if source:
        spider = resolve_source(source, registry)
        cats = [CategoryItem(**c) for c in spider.categories()]
        return [CategoriesResponse(
            source=source,
            supports_multi_genre=spider.supports_multi_genre,
            categories=cats,
        )]

    # All sources
    results: list[CategoriesResponse] = []
    for src_info in registry.list_sources():
        src_name = src_info["name"]
        spider = resolve_source(src_name, registry)
        cats = [CategoryItem(**c) for c in spider.categories()]
        results.append(CategoriesResponse(
            source=src_name,
            supports_multi_genre=spider.supports_multi_genre,
            categories=cats,
        ))
    return results

