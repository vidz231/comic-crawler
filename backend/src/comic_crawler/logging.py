"""Structured logging configuration using structlog and Rich."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from rich.console import Console

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with Rich console rendering.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return
    _CONFIGURED = True

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib logging (for third-party libs)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with an optional initial context.

    Args:
        name: Logger name (usually ``__name__``).
        **initial_context: Extra key-value pairs bound to every log entry.

    Returns:
        A structlog bound logger instance.
    """
    setup_logging()  # ensure configured
    return structlog.get_logger(name, **initial_context)  # type: ignore[return-value]
