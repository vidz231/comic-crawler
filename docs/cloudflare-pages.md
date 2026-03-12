# Cloudflare frontend deployment

This repository can be deployed to Cloudflare's free tier only for the `frontend` app.

The current `backend` service is a Python FastAPI crawler that depends on Playwright and other non-trivial Python runtime dependencies. That is not a practical fit for Cloudflare's free Workers/Pages runtime without a substantial rewrite of the API layer and scraping pipeline.

## What works on Cloudflare for free

- `frontend/` on Cloudflare
- Custom domain on Pages if you want one

## What does not fit the free Cloudflare path here

- `backend/` on Cloudflare Workers/Pages as-is
- Browser automation for scraping inside the free edge runtime

## Prerequisites

1. A separately hosted backend URL, for example `https://api.example.com`
2. Backend CORS updated to allow your Cloudflare hostname
3. Cloudflare auth configured locally with `npx wrangler login`

## Backend changes required before frontend deploy

Set `COMIC_CORS_ORIGINS` on the backend to include your frontend site, for example:

```env
COMIC_CORS_ORIGINS=["https://comic-crawler.workers.dev"]
```

## Wrangler deploy

This repo ships `frontend/wrangler.jsonc`, which already enables SPA fallback for static assets. Do not add a `dist/_redirects` rule when deploying with `wrangler deploy`.

```bash
cd frontend
cp .env.example .env
# Set VITE_API_BASE_URL to your backend origin, for example:
# VITE_API_BASE_URL=https://api.example.com
npm install
npx wrangler login
npm run deploy
```

## Recommended production shape

- Cloudflare: React PWA frontend
- Separate host: current FastAPI crawler API

If you want the whole stack on Cloudflare, that becomes a migration project rather than a deploy step.
