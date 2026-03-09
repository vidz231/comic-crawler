"""File storage abstraction for downloading and persisting comic images."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse

from comic_crawler.config import CrawlerConfig
from comic_crawler.exceptions import StorageError
from comic_crawler.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Storage protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class StorageBackend(Protocol):
    """Interface for persistence backends."""

    def save(self, data: bytes, path: Path) -> Path:
        """Write binary data to the given path. Returns the absolute path."""
        ...  # pragma: no cover

    def exists(self, path: Path) -> bool:
        """Check whether a file already exists at the given path."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------

class LocalStorage:
    """Save files to the local filesystem.

    Creates a hierarchical directory structure::

        <base_dir>/
        └── <series>/
            └── <chapter>/
                ├── 001.jpg
                ├── 002.jpg
                └── ...
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._log = get_logger("storage.local", base_dir=str(base_dir))

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def save(self, data: bytes, path: Path) -> Path:
        """Write binary data to a path relative to the base directory.

        Parent directories are created automatically.

        Args:
            data: Raw file bytes to write.
            path: Relative path within the base directory.

        Returns:
            Absolute path to the written file.

        Raises:
            StorageError: If the write operation fails.
        """
        full_path = self._base_dir / path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            self._log.debug("file_saved", path=str(full_path), size=len(data))
            return full_path
        except OSError as exc:
            raise StorageError(f"Failed to save file: {exc}") from exc

    def exists(self, path: Path) -> bool:
        """Check whether a file exists relative to the base directory."""
        return (self._base_dir / path).exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Remove or replace characters unsafe for filenames.

    Args:
        name: Original filename or path component.

    Returns:
        A filesystem-safe string.
    """
    sanitized = _UNSAFE_CHARS.sub("_", name).strip(". ")
    return sanitized or "untitled"


def build_image_path(
    series_title: str,
    chapter_number: float,
    page_number: int,
    image_url: str,
) -> Path:
    """Build a hierarchical file path for a comic page image.

    Args:
        series_title: Name of the comic series.
        chapter_number: Chapter number (e.g. 10 or 10.5).
        page_number: Page number (1-indexed).
        image_url: Original image URL (used to detect extension).

    Returns:
        A relative ``Path`` like ``series/chapter_010/001.jpg``.
    """
    # Detect extension from URL
    url_path = urlparse(image_url).path
    ext = Path(url_path).suffix or ".jpg"

    series_dir = sanitize_filename(series_title)
    chapter_dir = f"chapter_{chapter_number:06.1f}".replace(".", "_")
    filename = f"{page_number:03d}{ext}"

    return Path(series_dir) / chapter_dir / filename


def create_storage(config: CrawlerConfig) -> StorageBackend:
    """Create a storage backend based on configuration.

    Args:
        config: Crawler configuration.

    Returns:
        A configured storage backend instance.

    Raises:
        StorageError: If the backend type is unsupported.
    """
    if config.storage_backend == "local":
        return LocalStorage(config.output_dir)
    raise StorageError(f"Unsupported storage backend: {config.storage_backend}")
