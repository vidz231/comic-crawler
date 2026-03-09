"""Tests for the SourceCircuitBreaker."""

from __future__ import annotations

import pytest

from comic_crawler.spiders.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    SourceCircuitBreaker,
)


class TestCircuitBreakerStates:
    """Verify the CLOSED → OPEN → HALF_OPEN → CLOSED state machine."""

    def test_starts_closed(self):
        cb = SourceCircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.health_label() == "healthy"

    def test_success_keeps_closed(self):
        cb = SourceCircuitBreaker("test")
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == CircuitState.CLOSED

    def test_trips_open_after_threshold(self):
        cb = SourceCircuitBreaker("test", failure_threshold=3)

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(self._failing_func)

        assert cb.state == CircuitState.OPEN
        assert cb.health_label() == "down"

    def test_rejects_when_open(self):
        cb = SourceCircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: 42)

    def test_transitions_to_half_open_after_timeout(self):
        cb = SourceCircuitBreaker("test", failure_threshold=1, reset_timeout=0.0)
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        # With reset_timeout=0, the state property immediately transitions
        # from OPEN → HALF_OPEN on read
        import time
        time.sleep(0.01)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.health_label() == "degraded"

    def test_half_open_success_closes(self):
        cb = SourceCircuitBreaker(
            "test", failure_threshold=1, success_threshold=1, reset_timeout=0.0
        )
        # Trip it
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        import time
        time.sleep(0.01)

        # Should be HALF_OPEN, and a success should close it
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = SourceCircuitBreaker(
            "test", failure_threshold=1, reset_timeout=0.01
        )
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        import time
        time.sleep(0.02)  # Wait for reset_timeout to elapse

        # Should be HALF_OPEN now
        assert cb.state == CircuitState.HALF_OPEN

        # Fail again in HALF_OPEN — should reopen
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        # Access internal state directly (avoid auto-transition via property)
        assert cb._state == CircuitState.OPEN

    def test_manual_reset(self):
        cb = SourceCircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_get_stats(self):
        cb = SourceCircuitBreaker("test", failure_threshold=3)
        with pytest.raises(ValueError):
            cb.call(self._failing_func)

        stats = cb.get_stats()
        assert stats["state"] == "closed"  # only 1 failure, threshold is 3
        assert stats["consecutive_failures"] == 1
        assert stats["total_failures"] == 1
        assert stats["last_failure_time"] is not None

    @staticmethod
    def _failing_func():
        raise ValueError("intentional failure")


class TestCircuitBreakerEdgeCases:
    def test_passes_args_and_kwargs(self):
        cb = SourceCircuitBreaker("test")

        def add(a, b, extra=0):
            return a + b + extra

        result = cb.call(add, 3, 5, extra=2)
        assert result == 10

    def test_failures_below_threshold_stay_closed(self):
        cb = SourceCircuitBreaker("test", failure_threshold=5)
        for _ in range(4):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError))

        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        cb = SourceCircuitBreaker("test", failure_threshold=3)
        # 2 failures
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError))
        # 1 success resets
        cb.call(lambda: "ok")
        assert cb.failure_count == 0
