"""Crawler configuration via environment variables and .env files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from comic_crawler.exceptions import ConfigError


class CrawlerConfig(BaseSettings):
    """Central configuration for the comic crawler.

    Values can be set via environment variables prefixed with ``COMIC_``
    or via a ``.env`` file in the project root.
    """

    model_config = SettingsConfigDict(
        env_prefix="COMIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Crawl behaviour -------------------------------------------------------
    concurrency: int = Field(default=5, ge=1, le=50, description="Max concurrent requests")
    download_delay: float = Field(
        default=0.5, ge=0.0, description="Delay between requests in seconds"
    )
    source_rate_limits: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-source download delay overrides in seconds. "
            "E.g. {'mangadex': 0.2, 'asura': 1.0}"
        ),
    )
    max_retries: int = Field(default=3, ge=0, description="Max retries for failed requests")

    # -- Network ---------------------------------------------------------------
    proxy_list: list[str] = Field(default_factory=list, description="Proxy URLs for rotation")
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Comic-Crawler/0.1",
        description="Default User-Agent header",
    )

    # -- Storage ---------------------------------------------------------------
    output_dir: Path = Field(default=Path("output"), description="Base output directory")
    storage_backend: Literal["local"] = Field(
        default="local", description="Storage backend type"
    )

    # -- API -------------------------------------------------------------------
    rate_limit: str = Field(
        default="60/minute", description="API rate limit in slowapi format (e.g. '60/minute')"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins. Set to specific domains in production.",
    )

    # -- Logging ---------------------------------------------------------------
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ConfigError(
                f"Invalid log_level '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            )
        return upper

    @field_validator("output_dir", mode="before")
    @classmethod
    def _coerce_output_dir(cls, v: str | Path) -> Path:
        return Path(v)
