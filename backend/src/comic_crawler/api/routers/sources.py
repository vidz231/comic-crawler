"""Router: list available comic sources.

GET /api/v1/sources  — returns metadata + health for every registered source.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from comic_crawler.api.dependencies import get_registry
from comic_crawler.api.schemas import SourceInfo, SourcesResponse
from comic_crawler.spiders.registry import SpiderRegistry

router = APIRouter()


@router.get(
    "/sources",
    response_model=SourcesResponse,
    summary="List available comic sources",
    description=(
        "Returns the name, base URL, and health status of every registered source."
    ),
)
async def list_sources(
    registry: Annotated[SpiderRegistry, Depends(get_registry)],
) -> SourcesResponse:
    """Return all registered source spiders with health info."""
    items = [SourceInfo(**s) for s in registry.list_sources_with_health()]
    return SourcesResponse(sources=items)
