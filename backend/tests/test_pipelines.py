"""Tests for item processing pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from comic_crawler.pipelines import (
    DeduplicationPipeline,
    ExportPipeline,
    PipelineManager,
    ValidationPipeline,
)


# -- Test model for ValidationPipeline -----------------------------------------

class _TestItem(BaseModel):
    title: str = Field(..., min_length=1)
    url: str


# -- ValidationPipeline --------------------------------------------------------

class TestValidationPipeline:
    def test_valid_item_passes(self) -> None:
        pipe = ValidationPipeline(_TestItem)
        result = pipe.process_item({"title": "Test", "url": "https://example.com"})
        assert result is not None
        assert result["title"] == "Test"

    def test_invalid_item_returns_none(self) -> None:
        pipe = ValidationPipeline(_TestItem)
        result = pipe.process_item({"title": ""})  # empty title + missing url
        assert result is None

    def test_extra_fields_stripped(self) -> None:
        pipe = ValidationPipeline(_TestItem)
        result = pipe.process_item({
            "title": "Test",
            "url": "https://example.com",
            "extra": "ignored",
        })
        assert result is not None
        assert "extra" not in result


# -- DeduplicationPipeline -----------------------------------------------------

class TestDeduplicationPipeline:
    def test_first_item_passes(self) -> None:
        pipe = DeduplicationPipeline(key="url")
        item = {"url": "https://a.com", "title": "A"}
        assert pipe.process_item(item) is not None

    def test_duplicate_is_dropped(self) -> None:
        pipe = DeduplicationPipeline(key="url")
        item = {"url": "https://a.com", "title": "A"}
        pipe.process_item(item)
        assert pipe.process_item(item) is None

    def test_different_items_both_pass(self) -> None:
        pipe = DeduplicationPipeline(key="url")
        assert pipe.process_item({"url": "https://a.com"}) is not None
        assert pipe.process_item({"url": "https://b.com"}) is not None

    def test_item_without_key_passes(self) -> None:
        pipe = DeduplicationPipeline(key="url")
        assert pipe.process_item({"title": "No URL"}) is not None

    def test_seen_count(self) -> None:
        pipe = DeduplicationPipeline(key="url")
        pipe.process_item({"url": "https://a.com"})
        pipe.process_item({"url": "https://b.com"})
        pipe.process_item({"url": "https://a.com"})  # duplicate
        assert pipe.seen_count == 2

    def test_reset(self) -> None:
        pipe = DeduplicationPipeline(key="url")
        pipe.process_item({"url": "https://a.com"})
        pipe.reset()
        assert pipe.seen_count == 0
        # After reset, same item should pass again
        assert pipe.process_item({"url": "https://a.com"}) is not None


# -- ExportPipeline ------------------------------------------------------------

class TestExportPipeline:
    def test_accumulates_items(self, tmp_path: Path) -> None:
        pipe = ExportPipeline(output_dir=tmp_path)
        pipe.process_item({"a": 1})
        pipe.process_item({"b": 2})
        assert pipe.item_count == 2

    def test_export_json(self, tmp_path: Path) -> None:
        pipe = ExportPipeline(output_dir=tmp_path)
        pipe.process_item({"title": "Test"})
        path = pipe.export_json("test.json")
        assert path.exists()
        content = path.read_text()
        assert "Test" in content

    def test_export_jsonl(self, tmp_path: Path) -> None:
        pipe = ExportPipeline(output_dir=tmp_path)
        pipe.process_item({"title": "A"})
        pipe.process_item({"title": "B"})
        path = pipe.export_jsonl("test.jsonl")
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_export_creates_parent_dirs(self, tmp_path: Path) -> None:
        pipe = ExportPipeline(output_dir=tmp_path / "sub" / "dir")
        pipe.process_item({"title": "Test"})
        path = pipe.export_json("out.json")
        assert path.exists()


# -- PipelineManager -----------------------------------------------------------

class TestPipelineManager:
    def test_chains_pipelines(self, tmp_path: Path) -> None:
        manager = PipelineManager()
        manager.add(ValidationPipeline(_TestItem))
        manager.add(DeduplicationPipeline(key="url"))

        # Valid, unique item passes
        result = manager.process_item({"title": "Test", "url": "https://a.com"})
        assert result is not None

    def test_drops_invalid_item(self) -> None:
        manager = PipelineManager()
        manager.add(ValidationPipeline(_TestItem))

        result = manager.process_item({"title": ""})
        assert result is None

    def test_drops_duplicate_after_validation(self) -> None:
        manager = PipelineManager()
        manager.add(ValidationPipeline(_TestItem))
        manager.add(DeduplicationPipeline(key="url"))

        item = {"title": "Test", "url": "https://a.com"}
        assert manager.process_item(item) is not None
        assert manager.process_item(item) is None  # duplicate

    def test_process_items_batch(self) -> None:
        manager = PipelineManager()
        manager.add(DeduplicationPipeline(key="url"))

        items = [
            {"url": "https://a.com"},
            {"url": "https://b.com"},
            {"url": "https://a.com"},  # dup
        ]
        results = manager.process_items(items)
        assert len(results) == 2

    def test_fluent_add(self) -> None:
        manager = PipelineManager()
        result = manager.add(DeduplicationPipeline())
        assert result is manager
