"""API-level Pydantic schemas — request bodies and response envelopes.

These are intentionally decoupled from the internal domain models in
``comic_crawler.models`` so the HTTP contract can evolve independently.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = Field(..., examples=["healthy"])
    version: str = Field(..., examples=["0.1.0"])
    dependencies: dict[str, str] = Field(
        default_factory=dict, description="Status of external dependencies"
    )


class ErrorDetail(BaseModel):
    """Standard error envelope returned on 4xx / 5xx."""

    code: str = Field(..., examples=["validation_error"])
    message: str = Field(..., examples=["url field is required"])


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class SourceInfo(BaseModel):
    """Metadata about a single comic source."""

    name: str = Field(..., examples=["asura"])
    base_url: str = Field(..., examples=["https://asuracomic.net"])
    health: str = Field(default="healthy", examples=["healthy", "degraded", "down"])
    state: str = Field(default="closed", examples=["closed", "open", "half_open"])
    consecutive_failures: int = Field(default=0)
    total_failures: int = Field(default=0)


class SourcesResponse(BaseModel):
    """Response for GET /api/v1/sources."""

    sources: list[SourceInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------


class SeriesOut(BaseModel):
    """API representation of a comic series."""

    title: str
    url: str
    cover_url: str | None = None
    author: str | None = None
    genres: list[str] = Field(default_factory=list)
    status: str | None = None
    synopsis: str | None = None
    follower_count: int | None = None


class ChapterOut(BaseModel):
    """API representation of a single chapter."""

    series_title: str
    number: float
    title: str | None = None
    url: str
    date_published: datetime | None = None
    page_count: int | None = None


class PageOut(BaseModel):
    """API representation of a single page/image."""

    series_title: str
    chapter_number: float
    page_number: int
    image_url: str
    local_path: Path | None = None


# ---------------------------------------------------------------------------
# Comic Detail
# ---------------------------------------------------------------------------


class ComicDetailResponse(BaseModel):
    """Full detail of a comic series — metadata + chapter list."""

    source: str
    slug: str
    series: SeriesOut
    chapters: list[ChapterOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chapter Read
# ---------------------------------------------------------------------------


class ChapterReadResponse(BaseModel):
    """All page images for a single chapter."""

    source: str
    series_title: str
    chapter_number: float
    pages: list[PageOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Browse (lightweight search)
# ---------------------------------------------------------------------------


class SearchLiteItem(BaseModel):
    """A single series card from the listing page."""

    title: str
    slug: str
    url: str
    latest_chapter: float | None = None
    cover_url: str | None = None
    status: str | None = None
    rating: float | None = None


class SearchLiteResult(BaseModel):
    """Result of a lightweight browse/search — one listing page."""

    source: str
    series_count: int
    page: int = Field(default=1, ge=1, description="Current listing page number")
    has_next_page: bool = Field(default=False, description="Whether more pages are available")
    results: list[SearchLiteItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Multi-source search
# ---------------------------------------------------------------------------


class MultiSearchResult(BaseModel):
    """Aggregated search results from one or more sources."""

    total_count: int
    sources_queried: list[str] = Field(default_factory=list)
    results: list[SearchLiteResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trending / Popular
# ---------------------------------------------------------------------------


class TrendingItem(BaseModel):
    """A single entry in a trending / popular list."""

    rank: int | None = None
    """Position in ranked list (1-based). None for unranked cards (e.g. Asura 'today')."""

    title: str
    slug: str
    url: str
    cover_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    rating: float | None = None
    latest_chapter: float | None = None
    view_count: int | None = None
    """Total view count (TruyenVN only)."""


class TrendingResponse(BaseModel):
    """Response for GET /api/v1/trending."""

    source: str
    period: str
    """The requested period, e.g. 'today', 'weekly', 'trending', 'views'."""
    items: list[TrendingItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Categories / Genres
# ---------------------------------------------------------------------------


class CategoryItem(BaseModel):
    """A single genre/category entry."""

    name: str = Field(..., examples=["Action"])
    slug: str = Field(..., examples=["action"])


class CategoriesResponse(BaseModel):
    """Response for GET /api/v1/categories."""

    source: str
    supports_multi_genre: bool = Field(
        default=False,
        description="Whether this source supports filtering by multiple genres at once.",
    )
    categories: list[CategoryItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class RecommendationResponse(BaseModel):
    """Response for GET /api/v1/recommendations."""

    source: str
    slug: str
    recommendations: list[SearchLiteItem] = Field(default_factory=list)

