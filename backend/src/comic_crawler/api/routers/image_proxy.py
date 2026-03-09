"""Router: image proxy for hotlink-protected sources.

GET /api/v1/image-proxy?url=<encoded_url>

Fetches external images server-side using curl_cffi (Chrome TLS
impersonation) to bypass Cloudflare TLS fingerprinting and hotlink
protection on comic CDNs.
"""

from __future__ import annotations

import asyncio
import mimetypes
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Maximum image size we'll proxy (20 MB)
_MAX_IMAGE_SIZE = 20 * 1024 * 1024

# Allowed upstream content-type prefixes
_ALLOWED_CONTENT_TYPES = ("image/",)

# ---------------------------------------------------------------------------
# Domain allow-list + referer mapping
# ---------------------------------------------------------------------------

# Subdomains are matched automatically (e.g. "i178.hinhhinh.com" matches "hinhhinh.com").
_ALLOWED_DOMAINS: set[str] = {
    "truyenqqno.com",
    "truyenvua.com",
    "tintruyen.net",
    "hinhhinh.com",
    "hinhtruyen.com",
    # MangaKakalot / Manganato CDN
    "2xstorage.com",
}

# Map domain suffix → referer for hotlink bypass
_REFERER_MAP: dict[str, str] = {
    "truyenqqno.com": "https://truyenqqno.com/",
    "truyenvua.com": "https://truyenqqno.com/",
    "tintruyen.net": "https://truyenqqno.com/",
    "hinhhinh.com": "https://truyenqqno.com/",
    "hinhtruyen.com": "https://truyenqqno.com/",
    # MangaKakalot / Manganato CDN
    "2xstorage.com": "https://www.manganato.gg/",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_allowed(url: str) -> bool:
    """Check if the URL's host is in the allow-list."""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return any(host == d or host.endswith(f".{d}") for d in _ALLOWED_DOMAINS)


def _referer_for(url: str) -> str | None:
    """Return the referer to use for a given URL."""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return None
    for domain, referer in _REFERER_MAP.items():
        if host == domain or host.endswith(f".{domain}"):
            return referer
    return None


def _guess_media_type(url: str) -> str:
    """Guess the media type from the URL path."""
    path = urlparse(url).path
    mt, _ = mimetypes.guess_type(path)
    return mt or "image/jpeg"


def _fetch_image(url: str, referer: str | None) -> tuple[bytes, int, str]:
    """Fetch image using curl_cffi with Chrome TLS impersonation (sync).

    Returns:
        (body, status_code, content_type)

    Raises:
        ValueError: If the response exceeds _MAX_IMAGE_SIZE or has a
            non-image content-type.
    """
    from curl_cffi import requests

    headers: dict[str, str] = {
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }
    if referer:
        headers["Referer"] = referer

    resp = requests.get(url, impersonate="chrome", headers=headers, timeout=15)
    ct = resp.headers.get("content-type", _guess_media_type(url))

    # Validate content-type is an image
    ct_lower = ct.lower().split(";")[0].strip()
    if not any(ct_lower.startswith(prefix) for prefix in _ALLOWED_CONTENT_TYPES):
        raise ValueError(f"Upstream returned non-image content-type: {ct_lower}")

    # Validate response size
    body = resp.content
    if len(body) > _MAX_IMAGE_SIZE:
        raise ValueError(
            f"Image too large: {len(body)} bytes (max {_MAX_IMAGE_SIZE})"
        )

    return body, resp.status_code, ct


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/image-proxy",
    summary="Proxy external images",
    description=(
        "Fetches an external image server-side to bypass hotlink protection. "
        "Uses Chrome TLS impersonation to bypass Cloudflare fingerprinting. "
        "Only allows known comic-source domains."
    ),
    responses={
        200: {"content": {"image/*": {}}, "description": "The proxied image"},
        400: {"description": "Missing or disallowed URL"},
        502: {"description": "Upstream fetch failed"},
    },
)
async def image_proxy(
    url: str = Query(..., description="Fully-qualified image URL to proxy"),
) -> Response:
    """Stream an external image through the server."""
    if not url or not url.startswith("http"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid http(s) URL is required.",
        )

    if not _is_allowed(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain not in allow-list.",
        )

    referer = _referer_for(url)

    try:
        body, upstream_status, content_type = await asyncio.to_thread(
            _fetch_image, url, referer
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream fetch failed: {exc}",
        ) from exc

    if upstream_status >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream returned {upstream_status}",
        )

    return Response(
        content=body,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "Access-Control-Allow-Origin": "*",
        },
    )
