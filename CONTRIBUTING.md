# Contributing to Comic Crawler

Thank you for your interest in contributing! This guide will help you get started.

---

## Getting Started

### Docker (easiest)

```bash
git clone https://github.com/your-username/comic-crawler.git
cd comic-crawler
cp .env.example .env
make dev    # or: docker compose up --build
```

### Local Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
comic-crawler serve

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## How to Contribute

### 🐛 Bug Reports

1. Search [existing issues](../../issues) first to avoid duplicates
2. Use the **Bug Report** issue template
3. Include: steps to reproduce, expected vs actual behavior, environment details

### 💡 Feature Requests

1. Open an issue using the **Feature Request** template
2. Describe the problem you're trying to solve
3. Suggest a solution and any alternatives you've considered

### 🕷️ New Source (Spider)

Adding a new comic source is one of the best ways to contribute! See our [Source Template Guide](docs/source-template.md) for a step-by-step walkthrough.

1. Open an issue using the **New Source** template
2. Fork the repo and create a branch: `git checkout -b source/site-name`
3. Implement your spider in `backend/src/comic_crawler/spiders/`
4. Add tests in `backend/tests/`
5. Submit a PR

### 🔧 Pull Requests

1. **Fork** the repo and create a feature branch
2. Make your changes
3. Ensure all checks pass:
   ```bash
   make test       # pytest
   make lint       # ruff + eslint
   make typecheck  # mypy + tsc
   ```
4. Write or update tests as needed
5. Submit a PR using the PR template

---

## Code Style

### Backend (Python)

- **Formatter / Linter**: [ruff](https://docs.astral.sh/ruff/) — config in `pyproject.toml`
- **Type checker**: [mypy](https://mypy-lang.org/) with `--strict`
- **Tests**: [pytest](https://pytest.org/) with `pytest-asyncio`

```bash
cd backend
ruff check src/ tests/       # lint
ruff format src/ tests/      # format
mypy src/comic_crawler/      # type check
python -m pytest tests/ -v   # test
```

### Frontend (TypeScript)

- **Linter**: ESLint — config in `eslint.config.js`
- **Type checker**: TypeScript strict mode

```bash
cd frontend
npm run lint                 # eslint
npx tsc --noEmit            # type check
```

---

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add ComicK spider
fix: handle empty chapter list in mangadex
docs: update API table in README
test: add circuit breaker edge cases
chore: update dependencies
```

---

## Need Help?

- Open a [Discussion](../../discussions) for questions
- Check the [Source Template Guide](docs/source-template.md) for spider development
- Review existing spiders in `backend/src/comic_crawler/spiders/` for examples
