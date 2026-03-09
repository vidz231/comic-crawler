"""Router: comic detail and chapter reading.

GET /api/v1/comics/{source}/{slug}                    — series detail.
GET /api/v1/comics/{source}/{slug}/chapters/{number}   — read a chapter.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from comic_crawler.api.dependencies import get_registry, resolve_source
from comic_crawler.api.schemas import (
    ChapterOut,
    ChapterReadResponse,
    ComicDetailResponse,
    PageOut,
    SeriesOut,
)
from comic_crawler.exceptions import ComicCrawlerError
from comic_crawler.spiders.registry import SpiderRegistry

router = APIRouter()


def _build_series_out(raw_series: dict) -> SeriesOut:
    """Convert a raw series dict to ``SeriesOut``."""
    return SeriesOut(
        title=raw_series.get("title", ""),
        url=str(raw_series.get("url", "")),
        cover_url=str(raw_series["cover_url"]) if raw_series.get("cover_url") else None,
        author=raw_series.get("author"),
        genres=raw_series.get("genres", []),
        status=raw_series.get("status"),
        synopsis=raw_series.get("synopsis"),
        follower_count=raw_series.get("follower_count"),
    )


def _build_chapter_out(ch: dict) -> ChapterOut:
    """Convert a raw chapter dict to ``ChapterOut``."""
    date_published = ch.get("date_published")
    # Defensively handle unparseable date strings
    if isinstance(date_published, str):
        try:
            from datetime import datetime
            datetime.fromisoformat(date_published)
        except (ValueError, TypeError):
            date_published = None

    return ChapterOut(
        series_title=ch.get("series_title", ""),
        number=ch.get("number", 0),
        title=ch.get("title"),
        url=str(ch.get("url", "")),
        date_published=date_published,
        page_count=ch.get("page_count"),
    )


@router.get(
    "/comics/{source}/{slug}",
    response_model=ComicDetailResponse,
    summary="Get comic detail",
    description=(
        "Returns full series metadata and chapter list for a comic. "
        "The slug is the URL-safe identifier from the source site."
    ),
)
async def comic_detail(
    source: Annotated[str, Path(description="Source name (e.g. 'asura')")],
    slug: Annotated[str, Path(description="Series slug (e.g. 'solo-leveling-001')")],
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
) -> ComicDetailResponse:
    """Fetch full detail for a specific comic from a source."""
    spider = resolve_source(source, registry)
    try:
        raw = await asyncio.to_thread(spider.detail, slug)
    except ComicCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch comic detail: {exc}",
        ) from exc

    series_out = _build_series_out(raw.get("series", {}))
    chapters_out = [_build_chapter_out(ch) for ch in raw.get("chapters", [])]

    return ComicDetailResponse(
        source=source,
        slug=slug,
        series=series_out,
        chapters=chapters_out,
    )


@router.get(
    "/comics/{source}/{slug}/chapters/{number}",
    response_model=ChapterReadResponse,
    summary="Read a chapter",
    description=(
        "Returns all page images for a single chapter. "
        "Use this to render the reading experience."
    ),
)
async def read_chapter(
    source: Annotated[str, Path(description="Source name")],
    slug: Annotated[str, Path(description="Series slug")],
    number: Annotated[float, Path(description="Chapter number (supports decimals like 10.5)")],
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
) -> ChapterReadResponse:
    """Fetch all page images for a chapter."""
    spider = resolve_source(source, registry)
    try:
        pages_raw = await asyncio.to_thread(spider.read_chapter, slug, number)
    except ComicCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to read chapter: {exc}",
        ) from exc

    pages_out = [
        PageOut(
            series_title=pg.get("series_title", ""),
            chapter_number=pg.get("chapter_number", 0),
            page_number=pg.get("page_number", 1),
            image_url=str(pg.get("image_url", "")),
            local_path=pg.get("local_path"),
        )
        for pg in pages_raw
    ]

    # Derive series_title from the first page (or empty)
    series_title = pages_out[0].series_title if pages_out else ""

    return ChapterReadResponse(
        source=source,
        series_title=series_title,
        chapter_number=number,
        pages=pages_out,
    )
