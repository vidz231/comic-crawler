"""Router: trending / popular comics by source.

GET /api/v1/trending — fetch trending comics from a given source.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from comic_crawler.api.dependencies import get_registry, resolve_source
from comic_crawler.api.schemas import TrendingItem, TrendingResponse
from comic_crawler.exceptions import ComicCrawlerError
from comic_crawler.spiders.registry import SpiderRegistry

router = APIRouter()


# ---------------------------------------------------------------------------
# Period validation — centralised Depends
# ---------------------------------------------------------------------------


def _validate_period(
    source: str,
    period: str,
    registry: SpiderRegistry,
) -> str:
    """Validate *period* against the spider's ``trending_periods`` list.

    Raises:
        HTTPException 404: Unknown source.
        HTTPException 422: Period not supported by the given source.
    """
    spider = resolve_source(source, registry)
    allowed: list[str] = getattr(spider, "trending_periods", [])
    if period not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid period '{period}' for source '{source}'. "
                f"Supported periods: {allowed}"
            ),
        )
    return period


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/trending",
    response_model=TrendingResponse,
    summary="Get trending / popular comics",
    description=(
        "Returns trending or popular comics from a given source. "
        "The available ``period`` values depend on the source: "
        "**asura** supports ``today``, ``weekly``, ``monthly``, ``all``; "
        "**truyenvn** supports ``trending``, ``views``, ``rating``, ``new``."
    ),
)
async def get_trending(
    source: Annotated[str, Query(description="Source key, e.g. 'asura' or 'truyenvn'")],
    period: Annotated[str, Query(description="Trending period / sort mode")],
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
) -> TrendingResponse:
    """Fetch trending comics for *source* filtered by *period*."""
    # Resolve + validate (raises 404 / 422 as appropriate)
    spider = resolve_source(source, registry)
    validated_period = _validate_period(source, period, registry)

    try:
        raw_items: list[dict] = await asyncio.to_thread(
            spider.trending, validated_period
        )
    except ComicCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    items = [
        TrendingItem(
            rank=item.get("rank"),
            title=item.get("title", ""),
            slug=item.get("slug", ""),
            url=item.get("url", ""),
            cover_url=item.get("cover_url"),
            genres=item.get("genres", []),
            rating=item.get("rating"),
            latest_chapter=item.get("latest_chapter"),
            view_count=item.get("view_count"),
        )
        for item in raw_items
    ]

    return TrendingResponse(source=source, period=validated_period, items=items)
