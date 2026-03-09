"""Item processing pipelines for validation, deduplication, and export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Pipeline(Protocol):
    """Interface for item processing pipeline stages."""

    def process_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Process an item and return it, modify it, or return None to drop it."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Concrete pipelines
# ---------------------------------------------------------------------------

class ValidationPipeline:
    """Validate scraped items against a Pydantic model.

    Items that fail validation are dropped and logged.
    """

    def __init__(self, model: type[BaseModel]) -> None:
        self._model = model
        self._log = get_logger("pipeline.validation", model=model.__name__)

    def process_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        try:
            validated = self._model.model_validate(item)
            return validated.model_dump()
        except ValidationError as exc:
            self._log.warning(
                "validation_failed",
                errors=exc.error_count(),
                item_keys=list(item.keys()),
            )
            return None


class DeduplicationPipeline:
    """Filter duplicate items based on a specified key.

    Items whose key value has already been seen are silently dropped.
    """

    def __init__(self, key: str = "url") -> None:
        self._key = key
        self._seen: set[str] = set()
        self._log = get_logger("pipeline.dedup", key=key)

    def process_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        value = item.get(self._key)
        if value is None:
            return item  # can't dedup without the key

        value_str = str(value)
        if value_str in self._seen:
            self._log.debug("duplicate_dropped", value=value_str)
            return None

        self._seen.add(value_str)
        return item

    @property
    def seen_count(self) -> int:
        """Number of unique values tracked so far."""
        return len(self._seen)

    def reset(self) -> None:
        """Clear the deduplication cache."""
        self._seen.clear()


class ExportPipeline:
    """Collect items and export them to JSON / JSONL files."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._items: list[dict[str, Any]] = []
        self._log = get_logger("pipeline.export", output_dir=str(output_dir))

    def process_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Accumulate items for batch export."""
        self._items.append(item)
        return item

    def export_json(self, filename: str = "items.json", *, indent: bool = True) -> Path:
        """Write all accumulated items to a JSON file.

        Args:
            filename: Output filename.
            indent: Pretty-print the JSON.

        Returns:
            Path to the written file.
        """
        import json

        path = self._output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._items, f, ensure_ascii=False, indent=2 if indent else None, default=str)

        self._log.info("exported_json", path=str(path), count=len(self._items))
        return path

    def export_jsonl(self, filename: str = "items.jsonl") -> Path:
        """Write all accumulated items to a JSON Lines file.

        Args:
            filename: Output filename.

        Returns:
            Path to the written file.
        """
        import json

        path = self._output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            for item in self._items:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

        self._log.info("exported_jsonl", path=str(path), count=len(self._items))
        return path

    @property
    def item_count(self) -> int:
        """Number of accumulated items."""
        return len(self._items)


# ---------------------------------------------------------------------------
# Pipeline manager
# ---------------------------------------------------------------------------

class PipelineManager:
    """Chain multiple pipelines and process items through all of them.

    Pipelines are executed in order. If any pipeline returns ``None``,
    the item is dropped and subsequent pipelines are skipped.
    """

    def __init__(self, pipelines: list[Pipeline] | None = None) -> None:
        self._pipelines: list[Pipeline] = pipelines or []
        self._log = get_logger("pipeline.manager")

    def add(self, pipeline: Pipeline) -> "PipelineManager":
        """Append a pipeline stage. Returns self for chaining."""
        self._pipelines.append(pipeline)
        return self

    def process_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Run the item through all pipeline stages in order.

        Returns:
            The (possibly transformed) item, or ``None`` if dropped.
        """
        current: dict[str, Any] | None = item
        for pipeline in self._pipelines:
            if current is None:
                break
            current = pipeline.process_item(current)
        return current

    def process_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process a batch of items, filtering out dropped ones.

        Returns:
            List of items that survived all pipeline stages.
        """
        results: list[dict[str, Any]] = []
        for item in items:
            result = self.process_item(item)
            if result is not None:
                results.append(result)
        self._log.info(
            "batch_processed",
            input_count=len(items),
            output_count=len(results),
            dropped=len(items) - len(results),
        )
        return results
