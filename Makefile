# ──────────────────────────────────────────────────────────────────────────────
# Comic Crawler — Developer Makefile
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: dev down test lint typecheck format build clean help

## Start all services with Docker Compose (rebuild)
dev:
	docker compose up --build -d

## Stop all services
down:
	docker compose down

## Run backend tests
test:
	cd backend && python -m pytest tests/ -v

## Lint backend (ruff) + frontend (eslint)
lint:
	cd backend && ruff check src/ tests/
	cd frontend && npm run lint

## Type-check backend (mypy) + frontend (tsc)
typecheck:
	cd backend && mypy src/comic_crawler/
	cd frontend && npx tsc --noEmit

## Auto-format backend code
format:
	cd backend && ruff format src/ tests/

## Build Docker images without starting
build:
	docker compose build

## Stop services + remove volumes and local images
clean:
	docker compose down -v --rmi local

## Show this help
help:
	@echo ""
	@echo "  make dev        — Start all services (Docker Compose)"
	@echo "  make down       — Stop all services"
	@echo "  make test       — Run backend pytest"
	@echo "  make lint       — Lint backend + frontend"
	@echo "  make typecheck  — Type-check backend + frontend"
	@echo "  make format     — Auto-format backend code"
	@echo "  make build      — Build Docker images"
	@echo "  make clean      — Remove containers, volumes, images"
	@echo ""
