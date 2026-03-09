"""Data models for scraped comic content."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class ComicSeries(BaseModel):
    """Series-level metadata for a comic."""

    title: str = Field(..., min_length=1, description="Comic series title")
    url: HttpUrl = Field(..., description="Series landing page URL")
    cover_url: HttpUrl | None = Field(default=None, description="Cover image URL")
    author: str | None = Field(default=None, description="Author / artist name")
    genres: list[str] = Field(default_factory=list, description="Genre tags")
    status: str | None = Field(default=None, description="Publication status (ongoing, completed)")
    synopsis: str | None = Field(default=None, description="Series description / synopsis")
    follower_count: int | None = Field(default=None, ge=0, description="Number of followers")


class Chapter(BaseModel):
    """A single chapter within a comic series."""

    series_title: str = Field(..., min_length=1, description="Parent series title")
    number: float = Field(..., ge=0, description="Chapter number (supports 10.5 etc)")
    title: str | None = Field(default=None, description="Chapter title")
    url: HttpUrl = Field(..., description="Chapter page URL")
    date_published: datetime | None = Field(default=None, description="Publication date")
    page_count: int | None = Field(default=None, ge=0, description="Number of pages")


class Page(BaseModel):
    """A single page / image within a chapter."""

    series_title: str = Field(..., min_length=1, description="Parent series title")
    chapter_number: float = Field(..., ge=0, description="Parent chapter number")
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    image_url: HttpUrl = Field(..., description="Source image URL")
    local_path: Path | None = Field(default=None, description="Local file path after download")
