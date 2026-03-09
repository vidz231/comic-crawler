"""CLI entry point for comic-crawler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from comic_crawler.config import CrawlerConfig
from comic_crawler.logging import get_logger, setup_logging


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="comic-crawler",
        description="Comic web crawler built on Scrapling",
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="Path to .env config file"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Override output directory"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Set log level",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- list ---------------------------------------------------------------
    subparsers.add_parser("list", help="List available spiders")

    # -- asura --------------------------------------------------------------
    asura_parser = subparsers.add_parser("asura", help="Crawl asuracomic.net")
    asura_sub = asura_parser.add_subparsers(dest="asura_mode", help="Crawl mode")

    single_p = asura_sub.add_parser("single", help="Crawl a single series")
    single_p.add_argument("url", help="Full URL to the series page")
    single_p.add_argument(
        "--skip-chapters",
        action="store_true",
        default=False,
        help="Only fetch series metadata, skip chapter image crawling",
    )

    bulk_p = asura_sub.add_parser("bulk", help="Discover and crawl all series")
    bulk_p.add_argument(
        "--max-pages", type=int, default=0, help="Max search pages (0 = unlimited)"
    )

    search_p = asura_sub.add_parser("search", help="Search series metadata")
    search_p.add_argument("--max-pages", type=int, default=1)
    search_p.add_argument("--latest", type=int, default=5)
    search_p.add_argument("--name", type=str, default=None)

    browse_p = asura_sub.add_parser("browse", help="Fast browse listing page")
    browse_p.add_argument("--name", type=str, default=None)
    browse_p.add_argument("--page", type=int, default=1)

    # -- serve --------------------------------------------------------------
    serve_p = subparsers.add_parser("serve", help="Start the FastAPI HTTP server")
    serve_p.add_argument("--host", default="0.0.0.0", help="Bind address")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--reload", action="store_true", default=False)

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _handle_list() -> None:
    """List available spiders."""
    print("Available spiders:")
    print("  asura  — asuracomic.net (built-in)")
    print()
    print("Example:")
    print("  comic-crawler asura single https://asuracomic.net/series/...")
    print("  comic-crawler asura search --max-pages 2 --latest 3")
    print("  comic-crawler asura bulk --max-pages 5")


def _handle_asura(args: argparse.Namespace, config: CrawlerConfig) -> None:
    """Handle the 'asura' command and its sub-modes."""
    from comic_crawler.spiders.asura import AsuraSpider

    log = get_logger("cli")
    spider = AsuraSpider(config=config)

    if args.asura_mode == "single":
        log.info("asura_single_start", url=args.url)
        if args.skip_chapters:
            result = spider.parse_series(args.url)
            spider._export_results(result["series"]["title"], result)
        else:
            result = spider.run_single(args.url)
        log.info(
            "asura_single_complete",
            chapters=len(result.get("chapters", [])),
            pages=len(result.get("pages", [])),
        )

    elif args.asura_mode == "bulk":
        log.info("asura_bulk_start", max_pages=args.max_pages)
        results = spider.run_bulk(max_pages=args.max_pages)
        log.info("asura_bulk_complete", series_count=len(results))

    elif args.asura_mode == "search":
        log.info("asura_search_start", max_pages=args.max_pages, latest=args.latest)
        results = spider.run_search(
            max_pages=args.max_pages, latest_chapters=args.latest, name=args.name
        )
        log.info("asura_search_complete", series_count=len(results))

    elif args.asura_mode == "browse":
        log.info("asura_browse_start", page=args.page, name=args.name)
        result = spider.crawl_search_lite(page=args.page, name=args.name)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        log.info("asura_browse_complete", series_count=len(result["results"]))

    else:
        print(
            "Error: Specify 'single', 'bulk', 'search', or 'browse' mode.",
            file=sys.stderr,
        )
        sys.exit(1)


def _handle_serve(args: argparse.Namespace, config: CrawlerConfig) -> None:
    """Start the FastAPI HTTP server."""
    try:
        import uvicorn

        from comic_crawler.api.app import create_app
    except ImportError:
        print(
            "Error: FastAPI/uvicorn is not installed. "
            "Install the optional api extras:\n"
            "  pip install 'comic-crawler[api]'",
            file=sys.stderr,
        )
        sys.exit(1)

    log = get_logger("cli")
    app = create_app()
    log.info("api_server_starting", host=args.host, port=args.port, reload=args.reload)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=config.log_level.lower(),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main CLI entry point — dispatches to command handlers."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Build config
    config_kwargs: dict[str, object] = {}
    if args.output:
        config_kwargs["output_dir"] = args.output
    if args.log_level:
        config_kwargs["log_level"] = args.log_level

    config = CrawlerConfig(**config_kwargs)  # type: ignore[arg-type]
    setup_logging(config.log_level)

    handlers = {
        "list": lambda: _handle_list(),
        "asura": lambda: _handle_asura(args, config),
        "serve": lambda: _handle_serve(args, config),
    }

    handler = handlers.get(args.command)
    if handler:
        handler()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
