"""API middleware — request logging and trace IDs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("api.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, duration, and a trace ID."""

    async def dispatch(
        self, request: Request, call_next: Callable  # type: ignore[type-arg]
    ) -> Response:
        trace_id = uuid.uuid4().hex[:12]
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Trace-Id"] = trace_id

        await logger.ainfo(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=f"{duration_ms:.1f}",
            trace_id=trace_id,
        )

        structlog.contextvars.unbind_contextvars("trace_id")
        return response
