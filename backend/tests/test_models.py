"""Tests for data models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from comic_crawler.models import Chapter, ComicSeries, Page


class TestComicSeries:
    """Tests for the ComicSeries model."""

    def test_minimal_valid(self) -> None:
        series = ComicSeries(title="Test Comic", url="https://example.com/comic")
        assert series.title == "Test Comic"
        assert str(series.url) == "https://example.com/comic"

    def test_full_valid(self) -> None:
        series = ComicSeries(
            title="Test Comic",
            url="https://example.com/comic",
            cover_url="https://example.com/cover.jpg",
            author="Author Name",
            genres=["action", "comedy"],
            status="ongoing",
            synopsis="A great comic.",
        )
        assert series.author == "Author Name"
        assert series.genres == ["action", "comedy"]

    def test_empty_title_fails(self) -> None:
        with pytest.raises(ValidationError):
            ComicSeries(title="", url="https://example.com/comic")

    def test_invalid_url_fails(self) -> None:
        with pytest.raises(ValidationError):
            ComicSeries(title="Test", url="not-a-url")

    def test_defaults_are_none(self) -> None:
        series = ComicSeries(title="Test", url="https://example.com")
        assert series.cover_url is None
        assert series.author is None
        assert series.synopsis is None
        assert series.genres == []


class TestChapter:
    """Tests for the Chapter model."""

    def test_minimal_valid(self) -> None:
        chapter = Chapter(
            series_title="Test Comic",
            number=1.0,
            url="https://example.com/chapter/1",
        )
        assert chapter.number == 1.0

    def test_half_chapter_number(self) -> None:
        chapter = Chapter(
            series_title="Test Comic",
            number=10.5,
            url="https://example.com/chapter/10.5",
        )
        assert chapter.number == 10.5

    def test_with_date(self) -> None:
        dt = datetime(2024, 1, 15, 12, 0, 0)
        chapter = Chapter(
            series_title="Test Comic",
            number=1,
            url="https://example.com/chapter/1",
            date_published=dt,
        )
        assert chapter.date_published == dt

    def test_negative_number_fails(self) -> None:
        with pytest.raises(ValidationError):
            Chapter(
                series_title="Test",
                number=-1,
                url="https://example.com/ch",
            )

    def test_empty_series_title_fails(self) -> None:
        with pytest.raises(ValidationError):
            Chapter(series_title="", number=1, url="https://example.com/ch")


class TestPage:
    """Tests for the Page model."""

    def test_minimal_valid(self) -> None:
        page = Page(
            series_title="Test Comic",
            chapter_number=1,
            page_number=1,
            image_url="https://example.com/img/1.jpg",
        )
        assert page.page_number == 1
        assert page.local_path is None

    def test_with_local_path(self) -> None:
        page = Page(
            series_title="Test Comic",
            chapter_number=1,
            page_number=1,
            image_url="https://example.com/img/1.jpg",
            local_path=Path("/tmp/test/1.jpg"),
        )
        assert page.local_path == Path("/tmp/test/1.jpg")

    def test_zero_page_number_fails(self) -> None:
        with pytest.raises(ValidationError):
            Page(
                series_title="Test",
                chapter_number=1,
                page_number=0,
                image_url="https://example.com/1.jpg",
            )

    def test_invalid_image_url_fails(self) -> None:
        with pytest.raises(ValidationError):
            Page(
                series_title="Test",
                chapter_number=1,
                page_number=1,
                image_url="not-url",
            )
