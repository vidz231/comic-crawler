"""FastAPI application factory for comic-crawler.

Usage
-----
Start the server directly::

    python -m comic_crawler serve          # default: 0.0.0.0:8000
    comic-crawler serve --port 8080

Or import the app for testing / ASGI deployment::

    from comic_crawler.api.app import create_app
    app = create_app()
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from comic_crawler.api.dependencies import get_config
from comic_crawler.api.middleware import RequestLoggingMiddleware
from comic_crawler.api.routers import (
    categories,
    comics,
    image_proxy,
    recommendations,
    search,
    sources,
    trending,
)
from comic_crawler.api.schemas import ErrorDetail, HealthResponse
from comic_crawler.exceptions import ComicCrawlerError


_APP_VERSION = "0.1.0"

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler — startup / teardown hooks."""
    yield


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application.

    Importing this function (rather than a module-level ``app``) lets tests
    create fresh isolated instances.
    """
    config = get_config()

    app = FastAPI(
        title="Comic Crawler API",
        description=(
            "HTTP interface for the comic-crawler engine. "
            "Search comics across multiple sources, read chapters, "
            "and retrieve detailed series information over REST."
        ),
        version=_APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    # -- Rate limiting (slowapi) -------------------------------------------
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[config.rate_limit],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # -- CORS (configurable via COMIC_CORS_ORIGINS) ------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Request logging + trace IDs ---------------------------------------
    app.add_middleware(RequestLoggingMiddleware)

    # ------------------------------------------------------------------ Routes

    @app.get(
        "/livez",
        tags=["Health"],
        summary="Container liveness check",
    )
    async def livez() -> dict[str, str]:
        """Fast liveness check for container orchestration."""
        return {"status": "ok"}

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Service health check",
    )
    async def health() -> HealthResponse:
        """Returns 200 OK when the service is running."""
        deps: dict[str, str] = {}

        # Check Playwright browser availability
        try:
            from scrapling.engines.toolbelt import (  # type: ignore[import-untyped]
                check_if_engine_usable,
            )
            check_if_engine_usable("playwright")
            deps["playwright"] = "available"
        except Exception:
            deps["playwright"] = "unavailable"

        return HealthResponse(
            status="healthy",
            version=_APP_VERSION,
            dependencies=deps,
        )

    app.include_router(
        sources.router,
        prefix="/api/v1",
        tags=["Sources"],
    )
    app.include_router(
        search.router,
        prefix="/api/v1",
        tags=["Search"],
    )
    app.include_router(
        comics.router,
        prefix="/api/v1",
        tags=["Comics"],
    )
    app.include_router(
        trending.router,
        prefix="/api/v1",
        tags=["Trending"],
    )
    app.include_router(
        image_proxy.router,
        prefix="/api/v1",
        tags=["Images"],
    )
    app.include_router(
        categories.router,
        prefix="/api/v1",
        tags=["Categories"],
    )
    app.include_router(
        recommendations.router,
        prefix="/api/v1",
        tags=["Recommendations"],
    )


    # --------------------------------------------------------------- Error handlers

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        messages = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        return JSONResponse(
            status_code=422,
            content=ErrorDetail(
                code="validation_error", message=messages
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorDetail(
                code="http_error", message=str(exc.detail)
            ).model_dump(),
        )

    @app.exception_handler(ComicCrawlerError)
    async def crawler_error_handler(
        _request: Request, exc: ComicCrawlerError
    ) -> JSONResponse:
        log.warning("Upstream error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=502,
            content=ErrorDetail(
                code="upstream_error", message=str(exc)
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        log.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorDetail(
                code="internal_error",
                message="An unexpected error occurred.",
            ).model_dump(),
        )

    return app
