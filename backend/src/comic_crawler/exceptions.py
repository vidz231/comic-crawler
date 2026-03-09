"""Custom exception hierarchy for comic-crawler."""

from __future__ import annotations


class ComicCrawlerError(Exception):
    """Base exception for all comic-crawler errors."""

    def __init__(self, message: str = "", *, url: str | None = None) -> None:
        self.url = url
        super().__init__(message)


class FetchError(ComicCrawlerError):
    """Raised when a network request or fetcher operation fails."""

    def __init__(
        self,
        message: str = "Fetch failed",
        *,
        url: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.status_code = status_code
        super().__init__(message, url=url)


class ParseError(ComicCrawlerError):
    """Raised when HTML parsing or element extraction fails."""


class StorageError(ComicCrawlerError):
    """Raised when file I/O or download operations fail."""


class ConfigError(ComicCrawlerError):
    """Raised when configuration is invalid or missing."""


class BlockedError(FetchError):
    """Raised when anti-bot detection blocks a request."""

    def __init__(
        self,
        message: str = "Request blocked by anti-bot system",
        *,
        url: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message, url=url, status_code=status_code)
