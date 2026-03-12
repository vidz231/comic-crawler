# syntax=docker/dockerfile:1
# ============================================================
# Stage 1 — builder
#   Installs all Python dependencies into an isolated venv
# ============================================================
# PLAYWRIGHT_BROWSERS_PATH is set globally so both build and runtime
# stages use the same fixed location (not user-home-relative).
ARG PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed to compile some scrapling wheels (gcc, libxml2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt-dev \
        libffi-dev \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual env in a predictable location
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the packaging manifests first to leverage layer caching
COPY pyproject.toml ./
COPY src ./src

# Install the package with the [api] extras (FastAPI + uvicorn)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install ".[api]"


# ============================================================
# Stage 2 — runtime
#   Minimal image; copies venv + source from builder stage
# ============================================================
FROM python:3.12-slim AS runtime

# Install Playwright system dependencies (needed by scrapling[all])
# This installs Chromium + its deps in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Playwright / Chromium runtime deps
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        fonts-liberation \
        libgtk-3-0 \
        libx11-xcb1 \
        wget \
        ca-certificates \
        # Xvfb — virtual display so Chrome runs headed (CF detects headless)
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Playwright's Chromium browser binary.
# This layer is cached by Docker as long as the venv (above) hasn't changed.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN playwright install chromium \
 && chmod -R o+rX /opt/playwright-browsers




# Copy application source (required so the package is importable)
COPY src /app/src

# Security: run as non-root user
RUN groupadd --gid 1001 appgroup \
 && useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Volume for crawled output files
RUN mkdir -p /app/output && chown appuser:appgroup /app/output
VOLUME ["/app/output"]

USER appuser

# The app itself is installed in the venv pointing at /build/src, but we
# copied source to /app/src — tell Python where to find it.
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Ensure appuser finds the browsers installed above
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://localhost:{os.environ.get('PORT', '8000')}/health\")"

# Use --factory so create_app() is called fresh (allows env-based config)
CMD ["sh", "-c", "exec uvicorn comic_crawler.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --log-level info"]
