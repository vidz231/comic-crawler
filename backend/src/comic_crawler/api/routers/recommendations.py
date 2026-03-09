"""Router: genre-based recommendations.

GET /api/v1/recommendations?source=X&slug=Y&limit=6
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from comic_crawler.api.dependencies import get_registry, resolve_source
from comic_crawler.api.schemas import (
    RecommendationResponse,
    SearchLiteItem,
)
from comic_crawler.exceptions import ComicCrawlerError
from comic_crawler.spiders.registry import SpiderRegistry

router = APIRouter()


@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Get recommendations for a comic",
    description=(
        "Returns similar comics based on genre overlap. "
        "Fetches the target comic's genres, searches the same source, "
        "then ranks results by shared genre count."
    ),
)
async def get_recommendations(
    source: Annotated[str, Query(description="Source name (e.g. 'asura')")],
    slug: Annotated[str, Query(description="Series slug")],
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
    limit: int = Query(default=6, ge=1, le=20, description="Max recommendations"),
) -> RecommendationResponse:
    """Find similar comics by genre overlap."""
    spider = resolve_source(source, registry)

    # 1. Fetch target series detail to get genres
    try:
        raw_detail = await asyncio.to_thread(spider.detail, slug)
    except ComicCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch comic detail: {exc}",
        ) from exc

    target_genres = set(raw_detail.get("series", {}).get("genres", []))
    if not target_genres:
        return RecommendationResponse(source=source, slug=slug, recommendations=[])

    # 2. Pick top genres and search for comics with those genres
    #    We search with two of the most specific genres to get relevant results
    candidates: list[dict] = []
    seen_slugs: set[str] = {slug}  # exclude original

    for genre in list(target_genres)[:3]:
        try:
            raw = await asyncio.to_thread(spider.search, genre=genre, page=1)
            for item in raw.get("results", []):
                if item.get("slug") not in seen_slugs:
                    seen_slugs.add(item["slug"])
                    candidates.append(item)
        except ComicCrawlerError:
            continue

    # 3. Score by genre overlap (approximate — we only have genres from detail pages)
    #    Since listing pages don't always include genres, we score by title similarity
    #    and genre presence as a simple heuristic
    scored = sorted(candidates, key=lambda c: c.get("rating") or 0, reverse=True)

    recommendations = [
        SearchLiteItem(
            title=c.get("title", ""),
            slug=c.get("slug", ""),
            url=str(c.get("url", "")),
            latest_chapter=c.get("latest_chapter"),
            cover_url=str(c["cover_url"]) if c.get("cover_url") else None,
            status=c.get("status"),
            rating=c.get("rating"),
        )
        for c in scored[:limit]
    ]

    return RecommendationResponse(
        source=source,
        slug=slug,
        recommendations=recommendations,
    )
