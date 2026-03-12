# Comic Crawler

> Multi-source manga & webtoon reader — search, read, and download from 5+ sources with an offline-capable PWA frontend.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![Node](https://img.shields.io/badge/Node-18+-brightgreen.svg)](https://nodejs.org)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](docker-compose.yml)

---

## ✨ Features

- **Multi-source search** — query across all sources simultaneously
- **Webtoon & paged reader** — pinch-zoom, double-tap, keyboard navigation
- **Offline-first PWA** — download chapters, works without internet
- **Favorites & reading progress** — stored locally, JSON export/import backup
- **Anti-bot resilience** — Turnstile solver, `curl_cffi`, headless browser evasion
- **Self-hostable** — one-command Docker setup

---

## 🚀 Quick Start — Docker (Recommended)

```bash
git clone https://github.com/your-username/comic-crawler.git
cd comic-crawler
cp .env.example .env        # edit if needed
docker compose up --build -d
```

Open **http://localhost** — that's it!

> The API runs on port 8000 (internal only). Nginx in the frontend container reverse-proxies `/api/*` requests.

---

## 🛠️ Local Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
comic-crawler serve                # http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

The Vite dev server proxies `/api/*` to the backend automatically.

## ☁️ Cloudflare Deployment

The `frontend` app can be deployed on Cloudflare Pages' free tier. The current FastAPI + Playwright `backend` is not a practical fit for free Cloudflare Workers/Pages as-is.

See [docs/cloudflare-pages.md](docs/cloudflare-pages.md) for the deployable setup.

### Using Make

```bash
make dev          # docker compose up --build
make test         # run pytest
make lint         # ruff + eslint
make typecheck    # mypy + tsc
make format       # ruff format
```

---

## 🕷️ Supported Sources

| Key | Site | Type | Notes |
|-----|------|------|-------|
| `asura` | asuracomic.net | JS-rendered | Playwright |
| `truyenvn` | truyenvn.shop | HTTP | Server-rendered |
| `truyenqq` | truyenqq | HTTP | Server-rendered |
| `mangadex` | mangadex.org | JSON API | Official API |
| `mangakakalot` | manganato.gg | HTTP + solver | Turnstile bypass via Patchright |

---

## 📡 API

Interactive docs: **http://localhost:8000/docs**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `GET` | `/api/v1/sources` | List available sources |
| `GET` | `/api/v1/search` | Search across sources |
| `GET` | `/api/v1/browse` | Browse / listing page |
| `GET` | `/api/v1/trending` | Trending / popular comics |
| `GET` | `/api/v1/categories` | Genre categories |
| `GET` | `/api/v1/recommendations` | Genre-based recommendations |
| `GET` | `/api/v1/comics/{source}/{slug}` | Series details + chapter list |
| `GET` | `/api/v1/comics/{source}/{slug}/chapters/{chapter}` | Chapter page images |
| `GET` | `/api/v1/image-proxy` | Proxied image with cache headers |

---

## 🏗️ Architecture

```
comic-crawler/
├── backend/                  # Python + FastAPI
│   ├── src/comic_crawler/
│   │   ├── api/              # FastAPI app + 7 routers
│   │   ├── spiders/          # 5 source spiders + registry
│   │   └── turnstile/        # Cloudflare Turnstile solver
│   └── tests/                # 238 tests, 13 files
├── frontend/                 # React 19 + Vite PWA
│   └── src/
│       ├── pages/            # 4 pages (Home, Search, Detail, Reader)
│       ├── components/       # 33 components
│       └── hooks/            # 14 custom hooks
├── docker-compose.yml        # Production: api + nginx frontend
├── Makefile                  # dev, test, lint, build targets
└── roadmap/                  # 2-year open source roadmap
```

---

## 🧪 Development

```bash
# Run tests
cd backend && python -m pytest tests/ -v

# Type check
cd backend && mypy src/comic_crawler/

# Lint
cd backend && ruff check src/ tests/
cd frontend && npm run lint

# Format
cd backend && ruff format src/ tests/
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on bug reports, PRs, and writing new spiders.

To add a new source, check out the [source template guide](docs/source-template.md).

---

## 📜 License

MIT — see [LICENSE](LICENSE).
