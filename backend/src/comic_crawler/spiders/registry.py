"""Spider registry — source-agnostic spider discovery and dispatch.

Every comic source implements the ``SourceSpider`` protocol and registers
itself with the global ``SpiderRegistry``.  The API layer uses the registry
to resolve source names to spider instances at request time.

Auto-discovery
--------------
``create_default_registry`` scans all submodules of ``comic_crawler.spiders``
for a module-level ``SPIDER_CLASS`` attribute.  Any class found is instantiated
and registered automatically.  A manual fallback list is kept for spiders
that do not yet export ``SPIDER_CLASS``.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Protocol, runtime_checkable

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger
from comic_crawler.spiders.circuit_breaker import SourceCircuitBreaker

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SourceSpider(Protocol):
    """Contract that every comic source must satisfy.

    Implement these four properties / methods in your spider class and
    register it with ``SpiderRegistry`` to make it available to the API.
    """

    @property
    def name(self) -> str:
        """Unique, URL-safe source identifier (e.g. ``"asura"``)."""
        ...  # pragma: no cover

    @property
    def base_url(self) -> str:
        """Human-readable base URL of the source site."""
        ...  # pragma: no cover

    # -- Categories ----------------------------------------------------------

    def categories(self) -> list[dict[str, str]]:
        """Return the list of available genres/categories for this source.

        Returns a list of dicts with ``name`` (display label) and ``slug``
        (URL-safe identifier used for filtering).
        """
        ...  # pragma: no cover

    @property
    def supports_multi_genre(self) -> bool:
        """Whether this source supports filtering by multiple genres at once."""
        ...  # pragma: no cover

    # -- Search / browse -----------------------------------------------------

    def search(
        self,
        *,
        name: str | None = None,
        page: int = 1,
        genre: str | None = None,
    ) -> dict[str, Any]:
        """Paginated lightweight search.

        Returns a dict with ``results`` (list of card dicts), ``page``,
        ``has_next_page``, and ``series_count``.

        Args:
            name: Optional search query to filter by series name.
            page: Listing page number.
            genre: Optional genre slug to filter by category.
        """
        ...  # pragma: no cover

    # -- Detail --------------------------------------------------------------

    def detail(self, slug: str) -> dict[str, Any]:
        """Full series metadata + chapter list.

        Returns a dict with ``series`` and ``chapters`` keys.
        """
        ...  # pragma: no cover

    # -- Chapter read --------------------------------------------------------

    def read_chapter(
        self,
        slug: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Fetch all page images for a single chapter.

        Returns a list of page dicts with ``image_url``, ``page_number``, etc.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class SpiderRegistry:
    """Maps source names → spider instances.

    Each registered source gets an associated ``SourceCircuitBreaker``
    for health monitoring.

    Usage::

        registry = SpiderRegistry()
        registry.register(my_spider)
        spider = registry.get("asura")
    """

    def __init__(self) -> None:
        self._spiders: dict[str, SourceSpider] = {}
        self._breakers: dict[str, SourceCircuitBreaker] = {}

    def register(self, spider: SourceSpider) -> None:
        """Add a spider to the registry.

        Raises ``ValueError`` if a spider with the same name is already
        registered.
        """
        if spider.name in self._spiders:
            raise ValueError(f"Source '{spider.name}' is already registered")
        self._spiders[spider.name] = spider
        self._breakers[spider.name] = SourceCircuitBreaker(spider.name)
        log.info("source_registered", source=spider.name)

    def get(self, source: str) -> SourceSpider:
        """Look up a spider by source name.

        Raises ``KeyError`` if the source is not registered.
        """
        try:
            return self._spiders[source]
        except KeyError:
            raise KeyError(f"Unknown source: '{source}'") from None

    def execute(
        self, source: str, method: str, *args: Any, **kwargs: Any
    ) -> Any:
        """Call a spider method wrapped in the source's circuit breaker.

        Args:
            source: Source name.
            method: Method name on the spider (e.g. ``"search"``).
            *args, **kwargs: Forwarded to the method.

        Raises:
            KeyError: Unknown source.
            CircuitOpenError: Source is temporarily unavailable.
        """
        spider = self.get(source)
        breaker = self._breakers[source]
        func = getattr(spider, method)
        return breaker.call(func, *args, **kwargs)

    def list_sources(self) -> list[dict[str, str]]:
        """Return metadata for all registered sources."""
        return [
            {"name": s.name, "base_url": s.base_url}
            for s in self._spiders.values()
        ]

    def list_sources_with_health(self) -> list[dict[str, Any]]:
        """Return metadata + circuit breaker health for all sources."""
        results: list[dict[str, Any]] = []
        for s in self._spiders.values():
            breaker = self._breakers[s.name]
            results.append({
                "name": s.name,
                "base_url": s.base_url,
                **breaker.get_stats(),
            })
        return results

    def get_health(self, source: str) -> dict[str, Any]:
        """Return circuit breaker stats for a single source."""
        if source not in self._breakers:
            raise KeyError(f"Unknown source: '{source}'")
        return self._breakers[source].get_stats()

    def has(self, source: str) -> bool:
        """Check whether a source is registered."""
        return source in self._spiders


# ---------------------------------------------------------------------------
# Auto-Discovery
# ---------------------------------------------------------------------------


def _discover_spider_classes() -> list[type]:
    """Scan ``comic_crawler.spiders`` submodules for ``SPIDER_CLASS``."""
    import comic_crawler.spiders as spiders_pkg

    classes: list[type] = []
    for _importer, modname, _ispkg in pkgutil.iter_modules(
        spiders_pkg.__path__, prefix="comic_crawler.spiders."
    ):
        # Skip internal modules
        if modname.endswith(
            (
                ".registry",
                ".base_fetcher",
                ".http_json_spider",
                ".circuit_breaker",
                ".orchestrator",
                ".parser",
                ".search",
            )
        ):
            continue
        # Skip parser / search helpers (e.g. truyenvn_parser)
        basename = modname.rsplit(".", 1)[-1]
        if basename.endswith("_parser") or basename.endswith("_search"):
            continue

        try:
            mod = importlib.import_module(modname)
        except Exception:
            log.warning("spider_import_failed", module=modname, exc_info=True)
            continue

        cls = getattr(mod, "SPIDER_CLASS", None)
        if cls is not None:
            classes.append(cls)

    return classes


def create_default_registry(config: CrawlerConfig | None = None) -> SpiderRegistry:
    """Build a registry pre-loaded with all built-in sources.

    First attempts auto-discovery (modules exporting ``SPIDER_CLASS``),
    then falls back to manual imports for legacy spiders.
    """
    # Manual fallback imports for existing spiders without SPIDER_CLASS
    from comic_crawler.spiders.asura import AsuraSpider
    from comic_crawler.spiders.truyenqq import TruyenQQSpider
    from comic_crawler.spiders.truyenvn import TruyenVNSpider

    registry = SpiderRegistry()

    # 1. Auto-discovered spiders
    for cls in _discover_spider_classes():
        try:
            spider = cls(config=config)
            if not registry.has(spider.name):
                registry.register(spider)
        except Exception:
            log.warning("spider_init_failed", cls=cls.__name__, exc_info=True)

    # 2. Manual fallback — register only if not already discovered
    for spider_cls in (AsuraSpider, TruyenVNSpider, TruyenQQSpider):
        try:
            spider = spider_cls(config=config)
            if not registry.has(spider.name):
                registry.register(spider)
        except Exception:
            log.warning(
                "spider_fallback_failed",
                cls=spider_cls.__name__,
                exc_info=True,
            )

    return registry
