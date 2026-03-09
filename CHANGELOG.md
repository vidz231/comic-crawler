# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-03-09

### Added

- **Backend**: FastAPI application with 7 routers (sources, search, comics, trending, categories, recommendations, image-proxy)
- **Backend**: 5 comic source spiders — Asura, TruyenVN, TruyenQQ, MangaDex, MangaKakalot (manganato.gg)
- **Backend**: Spider auto-discovery registry with circuit breaker pattern
- **Backend**: BaseFetcher with HTTP ↔ Playwright dual fetch strategy
- **Backend**: HttpJsonSpider base class for JSON API sources
- **Backend**: Patchright-based Turnstile solver for Cloudflare bypass
- **Backend**: `curl_cffi` integration for TLS fingerprint impersonation
- **Backend**: Rate limiting (slowapi), CORS, structured errors, trace IDs
- **Backend**: Pydantic schemas for all API models
- **Frontend**: React 19 + Vite PWA with 4 lazy-loaded pages (Home, Search, Detail, Reader)
- **Frontend**: 33 components with glassmorphism design system
- **Frontend**: 14 custom hooks (favorites, reading progress, pinch-zoom, offline chapters, data backup, etc.)
- **Frontend**: Workbox service worker with 5 caching strategies
- **Frontend**: Webtoon and paged reader modes with pinch-zoom and double-tap zoom
- **Frontend**: Multi-source search with genre filtering
- **Frontend**: Offline chapter downloads and cache management
- **Frontend**: JSON export/import data backup
- **Frontend**: 30+ CSS design tokens (colors, typography, shape, shadows, motion)
- **Infra**: Production Docker Compose (API + Nginx frontend) with health checks
- **Infra**: Multi-stage Docker builds with pip cache mounts
- **Testing**: 238 tests across 13 files, ruff clean, mypy strict
- **Docs**: Source template guide (`docs/source-template.md`)
- **OSS**: LICENSE, CODE_OF_CONDUCT, CONTRIBUTING, SECURITY, CHANGELOG
- **OSS**: GitHub issue templates (bug, feature, new source) and PR template
- **DX**: Makefile with dev, test, lint, typecheck, format, build targets
