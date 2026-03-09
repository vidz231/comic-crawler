"""Per-source circuit breaker for fault tolerance.

Tracks consecutive failures per comic source and automatically degrades
unhealthy sources so a single broken site cannot block API responses.

States::

    CLOSED  →  normal operation, all calls forwarded
    OPEN    →  calls rejected immediately (source is down)
    HALF_OPEN → test recovery with a single call
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any

from comic_crawler.logging import get_logger

log = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class SourceCircuitBreaker:
    """Circuit breaker protecting a single comic source.

    Args:
        source_name: Human-readable source identifier for logging.
        failure_threshold: Consecutive failures before tripping open.
        success_threshold: Consecutive successes in half-open before closing.
        reset_timeout: Seconds to wait in open state before testing recovery.
    """

    def __init__(
        self,
        source_name: str,
        *,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        reset_timeout: float = 120.0,
    ) -> None:
        self.source_name = source_name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.reset_timeout = reset_timeout

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._total_failures = 0
        self._last_failure_time: float | None = None
        self._next_attempt_at = 0.0
        self._lock = threading.Lock()

    # -- Public API --------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may auto-transition from OPEN → HALF_OPEN)."""
        with self._lock:
            if self._state == CircuitState.OPEN and time.time() >= self._next_attempt_at:
                self._state = CircuitState.HALF_OPEN
                log.info(
                    "circuit_half_open",
                    source=self.source_name,
                    msg="Testing recovery",
                )
            return self._state

    @property
    def failure_count(self) -> int:
        return self._consecutive_failures

    @property
    def total_failures(self) -> int:
        return self._total_failures

    @property
    def last_failure_time(self) -> float | None:
        return self._last_failure_time

    def health_label(self) -> str:
        """Human-readable health label for the API."""
        state = self.state
        if state == CircuitState.CLOSED:
            return "healthy"
        if state == CircuitState.HALF_OPEN:
            return "degraded"
        return "down"

    def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with circuit breaker protection.

        Raises ``CircuitOpenError`` if the circuit is open and the
        reset timeout has not elapsed.
        """
        current = self.state  # may transition OPEN → HALF_OPEN

        if current == CircuitState.OPEN:
            raise CircuitOpenError(self.source_name)

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            log.info("circuit_reset", source=self.source_name)

    def get_stats(self) -> dict[str, Any]:
        """Snapshot of breaker stats for the health endpoint."""
        return {
            "state": self.state.value,
            "health": self.health_label(),
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "last_failure_time": self._last_failure_time,
        }

    # -- Internal ----------------------------------------------------------

    def _on_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._consecutive_successes += 1

            if (
                self._state == CircuitState.HALF_OPEN
                and self._consecutive_successes >= self.success_threshold
            ):
                self._state = CircuitState.CLOSED
                self._consecutive_successes = 0
                log.info(
                    "circuit_closed",
                    source=self.source_name,
                    msg="Recovered",
                )

    def _on_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            self._total_failures += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                log.warning(
                    "circuit_open",
                    source=self.source_name,
                    msg="Recovery failed — reopening",
                )
                self._trip()
            elif self._consecutive_failures >= self.failure_threshold:
                log.warning(
                    "circuit_open",
                    source=self.source_name,
                    failures=self._consecutive_failures,
                    msg="Failure threshold reached",
                )
                self._trip()

    def _trip(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._next_attempt_at = time.time() + self.reset_timeout


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        super().__init__(
            f"Source '{source_name}' is temporarily unavailable (circuit open)"
        )
