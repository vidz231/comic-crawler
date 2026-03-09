"""TruyenVN (Madara WordPress Theme) HTML parsing helpers.

Pure functions and a stateless parser class for extracting data from
Scrapling Adaptor responses.  No I/O, no side-effects.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://truyenvn.shop"
MANGA_PATH = "/truyen-tranh"

# Chapter slug pattern: "chapter-12", "chapter-10-5" (decimal via dash)
_CHAPTER_SLUG_RE = re.compile(r"chapter-(\d+(?:-\d+)?)")

# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------


# Vietnamese relative time units → timedelta kwargs
_VN_TIME_UNITS: dict[str, str] = {
    "giây": "seconds",
    "phút": "minutes",
    "giờ": "hours",
    "ngày": "days",
    "tuần": "weeks",
}

_RELATIVE_DATE_RE = re.compile(
    r"(\d+)\s+(" + "|".join(_VN_TIME_UNITS) + r")\s+trước"
)


def parse_relative_date(text: str) -> datetime | None:
    """Parse a Vietnamese relative date like '14 phút trước' into a datetime.

    Supports: giây (seconds), phút (minutes), giờ (hours),
    ngày (days), tuần (weeks).

    Returns:
        A ``datetime`` object, or ``None`` if parsing fails.
    """
    if not text:
        return None
    match = _RELATIVE_DATE_RE.search(text.strip())
    if not match:
        return None
    amount = int(match.group(1))
    unit_vn = match.group(2)
    unit_en = _VN_TIME_UNITS.get(unit_vn)
    if not unit_en:
        return None
    return datetime.now(UTC) - timedelta(**{unit_en: amount})


def abs_url(path: str) -> str:
    """Resolve a possibly-relative path against the TruyenVN base URL."""
    if path.startswith("http"):
        return path
    return urljoin(BASE_URL, path)


def parse_chapter_number_from_slug(slug: str) -> float:
    """Extract the chapter number from a Madara-style chapter slug.

    Examples::

        "chapter-12"   → 12.0
        "chapter-10-5" → 10.5
        "/truyen-tranh/some-slug/chapter-3/" → 3.0

    Raises:
        ParseError: If no chapter number is found.
    """
    match = _CHAPTER_SLUG_RE.search(slug)
    if not match:
        raise ParseError(f"Cannot extract chapter number from slug: {slug}", url=slug)
    raw = match.group(1)
    # "10-5" → "10.5"
    if "-" in raw:
        parts = raw.split("-", 1)
        return float(f"{parts[0]}.{parts[1]}")
    return float(raw)


# ---------------------------------------------------------------------------
# TruyenVNPageParser
# ---------------------------------------------------------------------------


class TruyenVNPageParser:
    """Stateless HTML parser for TruyenVN (Madara WP theme) pages.

    All methods accept a Scrapling ``Adaptor`` response and return
    parsed data.  No I/O, no fetching — pure extraction.
    """

    def __init__(self) -> None:
        self._log = get_logger("parser.truyenvn")

    # -- Series metadata ---------------------------------------------------

    def extract_series_title(self, response: Any) -> str:
        """Extract the series title from ``div.post-title h1``."""
        h1_els = response.css("div.post-title h1")
        if h1_els:
            text = (h1_els[0].text or "").strip()
            if text:
                return text

        # Fallback: <title> tag
        title_els = response.css("title")
        if title_els:
            raw = (title_els[0].text or "").strip()
            for suffix in (" - TruyenVN", " | TruyenVN"):
                if raw.endswith(suffix):
                    raw = raw[: -len(suffix)].strip()
            if raw:
                return raw

        raise ParseError("Could not find series title")

    def extract_synopsis(self, response: Any) -> str | None:
        """Extract the synopsis from ``div.summary__content``."""
        containers = response.css("div.summary__content")
        if not containers:
            containers = response.css("div.description-summary div.summary__content")
        if not containers:
            return None

        container = containers[0]
        # Text may be inside <p> or <span> children
        parts: list[str] = []
        for tag in ("p", "span"):
            for el in container.css(tag):
                text = (el.text or "").strip()
                if text and len(text) > 10:
                    parts.append(text)
            if parts:
                break

        # Fallback: direct container text
        if not parts:
            text = (container.text or "").strip()
            if text and len(text) > 10:
                parts.append(text)

        return " ".join(parts) if parts else None

    def extract_cover_url(self, response: Any) -> str | None:
        """Extract the cover image from ``div.summary_image img``."""
        images = response.css("div.summary_image img")
        for img in images:
            src = img.attrib.get("src", "") or img.attrib.get("data-src", "")
            if src:
                return abs_url(src)
        return None

    def extract_status(self, response: Any) -> str | None:
        """Extract series status from the post-content status block."""
        # Try specific status selectors
        for selector in [
            "div.post-status div.summary-content",
            "div.post-content_item.mg_status div.summary-content",
        ]:
            els = response.css(selector)
            for el in els:
                text = (el.text or "").strip()
                if text and text.lower() not in ("", "updating"):
                    return text.capitalize()
        return None

    def extract_genres(self, response: Any) -> list[str]:
        """Extract genre tags from genre content links."""
        genres: list[str] = []
        seen: set[str] = set()
        for selector in [
            "div.genres-content a",
            "div.post-content_item.mg_genres div.summary-content a",
        ]:
            links = response.css(selector)
            for link in links:
                text = (link.text or "").strip().rstrip(",").strip()
                if text and text not in seen:
                    seen.add(text)
                    genres.append(text)
            if genres:
                break
        return genres

    def extract_author(self, response: Any) -> str | None:
        """Extract the author from author-content."""
        for selector in [
            "div.author-content a",
            "div.post-content_item.mg_author div.summary-content a",
        ]:
            els = response.css(selector)
            for el in els:
                text = (el.text or "").strip()
                if text and text.lower() not in ("updating", ""):
                    return text
        return None

    def extract_artist(self, response: Any) -> str | None:
        """Extract the artist from artist-content."""
        for selector in [
            "div.artist-content a",
            "div.post-content_item.mg_artists div.summary-content a",
        ]:
            els = response.css(selector)
            for el in els:
                text = (el.text or "").strip()
                if text and text.lower() not in ("updating", ""):
                    return text
        return None

    def extract_rating(self, response: Any) -> float | None:
        """Extract the rating score."""
        for selector in ["div.post-total-rating span.score", "span.score"]:
            els = response.css(selector)
            for el in els:
                text = (el.text or "").strip()
                try:
                    val = float(text)
                    if val > 0:
                        return val
                except ValueError:
                    continue
        return None

    # -- Chapter list ------------------------------------------------------

    def extract_chapter_list(
        self,
        response: Any,
        series_title: str,
        series_url: str,
    ) -> list[dict[str, Any]]:
        """Extract all chapter entries from ``li.wp-manga-chapter``."""
        candidates: dict[float, dict[str, Any]] = {}

        chapter_items = response.css("li.wp-manga-chapter")
        for item in chapter_items:
            links = item.css("a")
            if not links:
                continue

            link = links[0]
            href = link.attrib.get("href", "")
            if not href:
                continue

            abs_href = abs_url(href)

            try:
                chapter_num = parse_chapter_number_from_slug(abs_href)
            except ParseError:
                continue

            chapter_title = (link.text or "").strip() or None

            # Release date (Vietnamese relative, e.g. "2 ngày trước")
            date_published = None
            date_els = item.css("span.chapter-release-date i")
            if not date_els:
                date_els = item.css("span.chapter-release-date")
            if date_els:
                raw_date = (date_els[0].text or "").strip()
                parsed_date = parse_relative_date(raw_date)
                if parsed_date:
                    date_published = parsed_date.isoformat()

            entry = {
                "series_title": series_title,
                "number": chapter_num,
                "title": chapter_title,
                "url": abs_href,
                "date_published": date_published,
                "page_count": None,
            }

            if chapter_num not in candidates:
                candidates[chapter_num] = entry

        chapters = sorted(candidates.values(), key=lambda c: c["number"])
        self._log.debug("chapters_extracted", count=len(chapters))
        return chapters

    # -- Chapter page images -----------------------------------------------

    def extract_page_images(
        self,
        response: Any,
        series_title: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Extract comic page images from ``div.reading-content``."""
        pages: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        page_number = 1

        images = response.css("div.reading-content div.page-break img")
        if not images:
            # Fallback: any img in reading-content
            images = response.css("div.reading-content img")

        for img in images:
            src = (
                img.attrib.get("src", "")
                or img.attrib.get("data-src", "")
            ).strip()
            if not src:
                continue

            abs_src = abs_url(src)

            # Skip common UI/nav images (use /segment/ matching to avoid
            # false-positives like 'ads' inside 'uploads')
            lower_src = abs_src.lower()
            if any(f"/{skip}" in lower_src for skip in ("thumb", "icon", "avatar", "logo", "banner")):
                continue

            if abs_src in seen_urls:
                continue
            seen_urls.add(abs_src)

            pages.append({
                "series_title": series_title,
                "chapter_number": chapter_number,
                "page_number": page_number,
                "image_url": abs_src,
                "local_path": None,
            })
            page_number += 1

        return pages

    # -- Search / browse ---------------------------------------------------

    def extract_series_cards(self, response: Any) -> list[dict[str, Any]]:
        """Extract search result cards from ``div.c-tabs-item__content``."""
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        cards = response.css("div.c-tabs-item__content")
        for card in cards:
            # Title + URL
            title_links = card.css("div.post-title h3 a")
            if not title_links:
                continue
            title_link = title_links[0]
            title = (title_link.text or "").strip()
            href = title_link.attrib.get("href", "")
            if not href:
                continue
            url = abs_url(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract slug from URL path
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            slug = path_parts[-1] if path_parts else ""

            # Cover image
            cover_url: str | None = None
            cover_imgs = card.css("div.tab-thumb img")
            if not cover_imgs:
                cover_imgs = card.css("img")
            for img in cover_imgs:
                src = img.attrib.get("src", "") or img.attrib.get("data-src", "")
                if src:
                    cover_url = abs_url(src)
                    break

            # Latest chapter
            latest_chapter: float | None = None
            latest_chapter_els = card.css("span.chapter a")
            if not latest_chapter_els:
                latest_chapter_els = card.css("span.font-meta.chapter a")
            if latest_chapter_els:
                ch_text = (latest_chapter_els[0].text or "").strip()
                ch_match = re.search(r"(\d+(?:\.\d+)?)", ch_text)
                if ch_match:
                    latest_chapter = float(ch_match.group(1))

            # Status
            status: str | None = None
            status_els = card.css("div.mg_status div.summary-content")
            if not status_els:
                status_els = card.css("div.post-content_item div.summary-content")
            if status_els:
                text = (status_els[0].text or "").strip()
                if text:
                    status = text.capitalize()

            # Rating
            rating: float | None = None
            score_els = card.css("span.score")
            if score_els:
                text = (score_els[0].text or "").strip()
                try:
                    val = float(text)
                    if val > 0:
                        rating = val
                except ValueError:
                    pass

            results.append({
                "title": title,
                "slug": slug,
                "url": url,
                "latest_chapter": latest_chapter,
                "cover_url": cover_url,
                "status": status,
                "rating": rating,
            })

        self._log.debug("series_cards_extracted", count=len(results))
        return results

    # -- Trending / Popular ---------------------------------------------------

    def extract_trending_cards(self, response: Any) -> list[dict[str, Any]]:
        """Extract trending comic cards from ``div.page-item-detail.manga``.

        Used for list pages accessed via ``?m_orderby=trending|views|rating|new-manga``.
        The card structure differs from search result cards (``div.c-tabs-item__content``).

        Returns:
            List of dicts with rank (1-based index), title, slug, url,
            cover_url, rating, view_count, latest_chapter.
        """
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        cards = response.css("div.page-item-detail.manga")
        if not cards:
            # Fallback: some theme versions use the same class without .manga
            cards = response.css("div.page-item-detail")

        for rank, card in enumerate(cards, start=1):
            # Title + URL
            title_links = card.css("div.post-title h3 a")
            if not title_links:
                title_links = card.css("div.post-title a")
            if not title_links:
                continue
            title_link = title_links[0]
            title = (title_link.text or "").strip()
            href = title_link.attrib.get("href", "")
            if not href:
                continue
            url = abs_url(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Slug from URL
            from urllib.parse import urlparse as _urlparse
            parsed = _urlparse(url)
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            slug = path_parts[-1] if path_parts else ""

            # Cover image
            cover_url: str | None = None
            for img in card.css("div.item-thumb img"):
                src = img.attrib.get("src", "") or img.attrib.get("data-src", "")
                if src:
                    cover_url = abs_url(src)
                    break

            # Rating
            rating: float | None = None
            for score_el in card.css("span#averagerate"):
                try:
                    rating = float((score_el.text or "").strip())
                except ValueError:
                    pass

            # View count — text adjacent to the eye icon
            view_count: int | None = None
            for item_div in card.css("div.item"):
                # The view count div contains an eye icon (i.ion-md-eye)
                if item_div.css("i.ion-md-eye"):
                    raw_views = (item_div.text or "").strip().replace(",", "").replace(".", "")
                    try:
                        view_count = int(raw_views)
                    except ValueError:
                        pass
                    break

            # Latest chapter
            latest_chapter: float | None = None
            for ch_link in card.css("span.chapter a"):
                ch_text = (ch_link.text or "").strip()
                ch_match = re.search(r"(\d+(?:\.\d+)?)", ch_text)
                if ch_match:
                    latest_chapter = float(ch_match.group(1))
                    break

            results.append({
                "rank": rank,
                "title": title,
                "slug": slug,
                "url": url,
                "cover_url": cover_url,
                "genres": [],
                "rating": rating,
                "latest_chapter": latest_chapter,
                "view_count": view_count,
            })

        self._log.debug("trending_cards_extracted", count=len(results))
        return results



    def extract_title_from_chapter_page(self, response: Any) -> str:
        """Extract the series title from a chapter page's <title> tag.

        Chapter pages have titles like:
        "Đọc Truyện Title Chapter N Tiếng Việt - TruyenVN"
        """
        title_els = response.css("title")
        if title_els:
            raw = (title_els[0].text or "").strip()
            # Remove site suffix
            for suffix in (" - TruyenVN", " | TruyenVN"):
                if raw.endswith(suffix):
                    raw = raw[: -len(suffix)].strip()
            # Remove "Đọc Truyện " prefix
            for prefix in ("Đọc Truyện ", "Doc Truyen "):
                if raw.startswith(prefix):
                    raw = raw[len(prefix):].strip()
            # Remove "Chapter N" and optional "Tiếng Việt" suffix
            raw = re.sub(
                r"\s+Chapter\s+\d+(?:\.\d+)?(?:\s+Tiếng Việt)?$",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip()
            if raw:
                return raw

        # Fallback: breadcrumb
        breadcrumbs = response.css("div.breadcrumb a")
        if len(breadcrumbs) >= 3:
            text = (breadcrumbs[-2].text or "").strip()
            if text:
                return text

        raise ParseError("Could not extract series title from chapter page")
