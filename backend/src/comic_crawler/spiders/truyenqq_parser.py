"""TruyenQQ (truyenqqno.com) HTML parsing helpers.

Pure functions and a stateless parser class for extracting data from
Scrapling Adaptor responses.  No I/O, no side-effects.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin, urlparse

from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://truyenqqno.com"
MANGA_PATH = "/truyen-tranh"
SEARCH_ENDPOINT = f"{BASE_URL}/frontend/search/search"

# Chapter URL pattern: "...-chap-12.html", "...-chap-10.5.html"
_CHAPTER_URL_RE = re.compile(r"-chap-(\d+(?:\.\d+)?)\.html")

# Vietnamese relative time units → timedelta kwargs
_VN_TIME_UNITS: dict[str, str] = {
    "giây": "seconds",
    "phút": "minutes",
    "giờ": "hours",
    "ngày": "days",
    "tuần": "weeks",
    "tháng": "days",  # approximate: 1 month ≈ 30 days
}

_RELATIVE_DATE_RE = re.compile(
    r"(\d+)\s+(" + "|".join(_VN_TIME_UNITS) + r")\s+trước"
)

_ABSOLUTE_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------


def parse_date(text: str) -> datetime | None:
    """Parse a Vietnamese date string into a datetime.

    Supports relative dates like '14 phút trước' and absolute dates
    like '01/02/2026' (DD/MM/YYYY).
    """
    if not text:
        return None
    text = text.strip()

    # Try relative date first
    match = _RELATIVE_DATE_RE.search(text)
    if match:
        amount = int(match.group(1))
        unit_vn = match.group(2)
        unit_en = _VN_TIME_UNITS.get(unit_vn)
        if not unit_en:
            return None
        if unit_vn == "tháng":
            amount *= 30
        return datetime.now(UTC) - timedelta(**{unit_en: amount})

    # Try absolute date (DD/MM/YYYY)
    match = _ABSOLUTE_DATE_RE.search(text)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(year, month, day, tzinfo=UTC)
        except ValueError:
            return None

    return None


def abs_url(path: str) -> str:
    """Resolve a possibly-relative path against the TruyenQQ base URL."""
    if path.startswith("http"):
        return path
    return urljoin(BASE_URL, path)


def parse_chapter_number_from_url(url: str) -> float:
    """Extract the chapter number from a TruyenQQ chapter URL.

    Examples::

        "...-chap-12.html"   → 12.0
        "...-chap-10.5.html" → 10.5

    Raises:
        ParseError: If no chapter number is found.
    """
    match = _CHAPTER_URL_RE.search(url)
    if not match:
        raise ParseError(f"Cannot extract chapter number from URL: {url}", url=url)
    return float(match.group(1))


def slug_from_url(url: str) -> str:
    """Extract the series slug (slug-id) from a TruyenQQ URL.

    Examples::

        "/truyen-tranh/cau-be-cua-than-chet-9441" → "cau-be-cua-than-chet-9441"
        "/truyen-tranh/slug-9441-chap-10.html"     → "slug-9441"

    The slug includes the numeric ID suffix required for URL construction.
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = [p for p in path.split("/") if p]

    if len(parts) >= 2 and parts[0] == "truyen-tranh":
        segment = parts[1]
    elif len(parts) == 1:
        segment = parts[0]
    else:
        raise ParseError(f"Cannot extract slug from URL: {url}", url=url)

    # Remove chapter suffix if present: "-chap-N.html"
    segment = re.sub(r"-chap-\d+(?:\.\d+)?\.html$", "", segment)
    return segment


# ---------------------------------------------------------------------------
# TruyenQQPageParser
# ---------------------------------------------------------------------------


class TruyenQQPageParser:
    """Stateless HTML parser for TruyenQQ (truyenqqno.com) pages.

    All methods accept a Scrapling ``Adaptor`` response and return
    parsed data.  No I/O, no fetching — pure extraction.
    """

    def __init__(self) -> None:
        self._log = get_logger("parser.truyenqq")

    # -- Series metadata ---------------------------------------------------

    def extract_series_title(self, response: Any) -> str:
        """Extract the series title from ``h1``."""
        h1_els = response.css("h1")
        if h1_els:
            text = (h1_els[0].text or "").strip()
            if text:
                return text

        # Fallback: <title> tag
        title_els = response.css("title")
        if title_els:
            raw = (title_els[0].text or "").strip()
            for suffix in (" - TruyenQQ", " | TruyenQQ"):
                if raw.endswith(suffix):
                    raw = raw[: -len(suffix)].strip()
            if raw:
                return raw

        raise ParseError("Could not find series title")

    def extract_synopsis(self, response: Any) -> str | None:
        """Extract the synopsis from ``div.detail-content p``."""
        # Primary: <p> paragraphs inside the detail-content div
        for selector in [
            "div.detail-content p",
            "div.story-detail-info p",
        ]:
            paragraphs = response.css(selector)
            parts: list[str] = []
            for p in paragraphs:
                text = (p.text or "").strip()
                if text and len(text) > 10:
                    # Clean up — remove genre/author references that got pulled in
                    parts.append(text)
            if parts:
                return " ".join(parts)

        return None

    def extract_cover_url(self, response: Any) -> str | None:
        """Extract the cover image from ``.book_avatar img``."""
        for selector in ["div.book_avatar img", ".book_avatar img"]:
            images = response.css(selector)
            for img in images:
                src = (
                    img.attrib.get("data-src", "")
                    or img.attrib.get("src", "")
                ).strip()
                if src and not src.endswith(".svg"):
                    return abs_url(src)
        return None

    def extract_status(self, response: Any) -> str | None:
        """Extract series status from ``li.status p.col-xs-9``."""
        # Primary: li.status row > p.col-xs-9
        els = response.css("li.status p.col-xs-9")
        for el in els:
            text = (el.text or "").strip()
            if text:
                return text

        # Fallback: look for the fa-rss icon pattern
        info_items = response.css("ul.list-info li")
        for item in info_items:
            label = (item.text or "").lower()
            if "tình trạng" in label:
                vals = item.css("p.col-xs-9")
                if vals:
                    text = (vals[0].text or "").strip()
                    if text:
                        return text
        return None

    def extract_genres(self, response: Any) -> list[str]:
        """Extract genre tags from ``ul.list01 li a``."""
        genres: list[str] = []
        seen: set[str] = set()
        for selector in [
            "ul.list01 li a",
            "li.kind p.col-xs-9 a",
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
        """Extract the author from ``li.author p.col-xs-9 a``."""
        # Primary: author li
        els = response.css("li.author p.col-xs-9 a")
        for el in els:
            text = (el.text or "").strip()
            if text and text.lower() not in ("đang cập nhật", ""):
                return text

        # Fallback: look for author via class/text
        els = response.css("li.author p.col-xs-9")
        for el in els:
            text = (el.text or "").strip()
            if text and text.lower() not in ("đang cập nhật", ""):
                return text
        return None

    def extract_rating(self, response: Any) -> float | None:
        """Extract the rating score."""
        for selector in ["span.rate-score", ".rate-score"]:
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
        """Extract all chapter entries from ``div.works-chapter-item``."""
        candidates: dict[float, dict[str, Any]] = {}

        chapter_items = response.css("div.works-chapter-item")
        if not chapter_items:
            chapter_items = response.css(".works-chapter-item")

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
                chapter_num = parse_chapter_number_from_url(abs_href)
            except ParseError:
                continue

            chapter_title = (link.text or "").strip() or None

            # Release date (DD/MM/YYYY or relative)
            date_published = None
            date_els = item.css(".time-chap")
            if date_els:
                raw_date = (date_els[0].text or "").strip()
                parsed_date = parse_date(raw_date)
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
        """Extract comic page images from the chapter reader."""
        pages: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        page_number = 1

        # Primary: images inside .chapter_content (excluding ads)
        images = response.css("div.chapter_content img")
        if not images:
            images = response.css(".page-chapter img")
        if not images:
            images = response.css("#chapter_content img")

        for img in images:
            img_class = img.attrib.get("class", "").lower()
            if any(ad in img_class for ad in ("ads", "banner", "popup")):
                continue

            src = (
                img.attrib.get("src", "")
                or img.attrib.get("data-src", "")
                or img.attrib.get("data-original", "")
            ).strip()
            if not src:
                continue

            lower_src = src.lower()
            if any(skip in lower_src for skip in ("ads", "banner", "logo", "icon", "avatar", "popup")):
                continue

            abs_src = abs_url(src)

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

    # -- Search (AJAX results) ---------------------------------------------

    def extract_search_results(self, response: Any) -> list[dict[str, Any]]:
        """Extract search results from the AJAX search endpoint HTML fragment.

        The AJAX endpoint ``POST /frontend/search/search`` returns an HTML
        fragment with ``<li>`` items, each containing:
        - ``a[href]`` → comic URL
        - ``div.search_avatar img`` → cover
        - ``p.name`` → title
        - ``p`` (third) → latest chapter like "Chương 110"
        """
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        items = response.css("li")
        for item in items:
            links = item.css("a")
            if not links:
                continue

            link = links[0]
            href = link.attrib.get("href", "")
            if not href or "truyen-tranh" not in href:
                continue

            url = abs_url(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Title from p.name
            title = ""
            name_els = item.css("p.name")
            if name_els:
                title = (name_els[0].text or "").strip()

            if not title:
                continue

            # Slug
            try:
                comic_slug = slug_from_url(url)
            except ParseError:
                continue

            # Cover image
            cover_url: str | None = None
            cover_imgs = item.css("div.search_avatar img")
            if not cover_imgs:
                cover_imgs = item.css("img")
            for cimg in cover_imgs:
                src = (
                    cimg.attrib.get("data-src", "")
                    or cimg.attrib.get("src", "")
                ).strip()
                if src and not src.endswith(".svg"):
                    cover_url = abs_url(src)
                    break

            # Latest chapter from the third <p>
            latest_chapter: float | None = None
            p_tags = item.css("p")
            for p in p_tags:
                text = (p.text or "").strip()
                ch_match = re.search(r"(?:Chương|Chapter|Chap)\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
                if ch_match:
                    latest_chapter = float(ch_match.group(1))
                    break

            results.append({
                "title": title,
                "slug": comic_slug,
                "url": url,
                "latest_chapter": latest_chapter,
                "cover_url": cover_url,
                "status": None,
                "rating": None,
            })

        self._log.debug("search_results_extracted", count=len(results))
        return results

    # -- Browse / listing --------------------------------------------------

    def extract_series_cards(self, response: Any) -> list[dict[str, Any]]:
        """Extract series cards from ``ul.list_grid li``.

        Used for browse pages and trending listings.
        """
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        # Collect li items from all list_grid elements
        grids = response.css("ul.list_grid")
        items: list[Any] = []
        for grid in grids:
            items.extend(grid.css("li"))

        if not items:
            # Fallback: direct li search
            items = response.css(".list_grid li")

        for card in items:
            # Title + URL — primary: h3 a, then a[title]
            title_links = card.css("h3 a")
            if not title_links:
                title_links = card.css("a[title]")
            if not title_links:
                # Skip items without a clear title link
                all_links = card.css("a")
                title_links = [
                    l for l in all_links
                    if "truyen-tranh" in l.attrib.get("href", "")
                       and (l.text or "").strip()
                ]
            if not title_links:
                continue

            title_link = title_links[0]
            title = (title_link.attrib.get("title", "") or (title_link.text or "")).strip()
            href = title_link.attrib.get("href", "")
            if not href:
                continue
            url = abs_url(href)

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract slug from URL
            try:
                comic_slug = slug_from_url(url)
            except ParseError:
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.strip("/").split("/") if p]
                comic_slug = path_parts[-1] if path_parts else ""

            # Cover image — prefer data-src (lazy-loaded real image) over src (placeholder)
            cover_url: str | None = None
            cover_imgs = card.css("img")
            for cimg in cover_imgs:
                src = (
                    cimg.attrib.get("data-src", "")
                    or cimg.attrib.get("src", "")
                ).strip()
                if src and "ads" not in src.lower() and not src.endswith(".svg"):
                    cover_url = abs_url(src)
                    break

            # Latest chapter
            latest_chapter: float | None = None
            ch_links = card.css(".last_chapter a")
            if not ch_links:
                ch_links = card.css("a[href*='chap-']")
            if ch_links:
                ch_text = (ch_links[0].text or "").strip()
                ch_match = re.search(r"(\d+(?:\.\d+)?)", ch_text)
                if ch_match:
                    latest_chapter = float(ch_match.group(1))

            results.append({
                "title": title,
                "slug": comic_slug,
                "url": url,
                "latest_chapter": latest_chapter,
                "cover_url": cover_url,
                "status": None,
                "rating": None,
            })

        self._log.debug("series_cards_extracted", count=len(results))
        return results

    # -- Trending (same structure as cards, but with rank) -----------------

    def extract_trending_cards(self, response: Any) -> list[dict[str, Any]]:
        """Extract trending cards from top listing pages.

        Returns:
            List of dicts with rank, title, slug, url, cover_url,
            genres, rating, latest_chapter, view_count.
        """
        cards = self.extract_series_cards(response)
        items: list[dict[str, Any]] = []
        for rank, card in enumerate(cards, start=1):
            items.append({
                "rank": rank,
                "title": card["title"],
                "slug": card["slug"],
                "url": card["url"],
                "cover_url": card.get("cover_url"),
                "genres": [],
                "rating": card.get("rating"),
                "latest_chapter": card.get("latest_chapter"),
                "view_count": None,
            })
        self._log.debug("trending_cards_extracted", count=len(items))
        return items

    # -- Title from chapter page -------------------------------------------

    def extract_title_from_chapter_page(self, response: Any) -> str:
        """Extract the series title from a chapter page's <title> tag.

        Chapter pages have titles like:
        "Tên truyện Chương N - TruyenQQ"
        """
        title_els = response.css("title")
        if title_els:
            raw = (title_els[0].text or "").strip()
            # Remove site suffix
            for suffix in (" - TruyenQQ", " | TruyenQQ", " - Truyện QQ"):
                if raw.endswith(suffix):
                    raw = raw[: -len(suffix)].strip()
            # Remove "Chương N" or "Chap N" suffix
            raw = re.sub(
                r"\s+(?:Chương|Chap|Chapter)\s+\d+(?:\.\d+)?.*$",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip()
            if raw:
                return raw

        # Fallback: breadcrumb
        breadcrumbs = response.css("ol.breadcrumb li a")
        if not breadcrumbs:
            breadcrumbs = response.css("div.breadcrumb a")
        if len(breadcrumbs) >= 2:
            text = (breadcrumbs[-2].text or "").strip()
            if text:
                return text

        raise ParseError("Could not extract series title from chapter page")
