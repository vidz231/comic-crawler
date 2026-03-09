"""Asura HTML parsing helpers — extracted from AsuraSpider.

Pure functions and a stateless parser class for extracting data from
Scrapling Adaptor responses. No I/O, no side-effects.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from comic_crawler.exceptions import ParseError
from comic_crawler.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://asuracomic.net"
SERIES_PATH = "/series"
CDN_DOMAIN = "gg.asuracomic.net"

# Known comic-type badge labels that should NOT be treated as titles.
_TYPE_LABELS = {"manhwa", "manga", "manhua", "novel", "poster"}

# Regex to extract chapter number from URL path: /chapter/12 or /chapter/10.5
_CHAPTER_NUM_RE = re.compile(r"/chapter/(\d+(?:\.\d+)?)/?$")

# Common date formats on Asura (e.g. "January 31st 2026", "February 3rd 2026")
_ORDINAL_SUFFIX_RE = re.compile(r"(\d+)(st|nd|rd|th)")

# Month pattern for date extraction from link text
_MONTH_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+"
    r"\d+(?:st|nd|rd|th)\s+\d{4}"
)


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------


def parse_chapter_number(url: str) -> float:
    """Extract the chapter number from a chapter URL.

    Args:
        url: Chapter URL like ``/series/{slug}/chapter/12``.

    Returns:
        Chapter number as a float (supports decimals like 10.5).

    Raises:
        ParseError: If no chapter number is found.
    """
    match = _CHAPTER_NUM_RE.search(url)
    if not match:
        raise ParseError(f"Cannot extract chapter number from URL: {url}", url=url)
    return float(match.group(1))


def parse_asura_date(date_str: str) -> datetime | None:
    """Parse an Asura-style date string like ``'January 31st 2026'``.

    Returns:
        A ``datetime`` object, or ``None`` if parsing fails.
    """
    if not date_str or not date_str.strip():
        return None
    # Remove ordinal suffixes: "31st" → "31"
    cleaned = _ORDINAL_SUFFIX_RE.sub(r"\1", date_str.strip())
    try:
        return datetime.strptime(cleaned, "%B %d %Y")
    except ValueError:
        log.debug("date_parse_failed", raw=date_str, cleaned=cleaned)
        return None


def abs_url(path: str) -> str:
    """Resolve a possibly-relative path against the Asura base URL."""
    if path.startswith("http"):
        return path
    return urljoin(BASE_URL, path)


# Backward-compatible alias
_abs_url = abs_url


# ---------------------------------------------------------------------------
# AsuraPageParser
# ---------------------------------------------------------------------------


class AsuraPageParser:
    """Stateless HTML parser for Asura pages.

    All methods accept a Scrapling ``Adaptor`` response and return
    parsed data. No I/O, no fetching — pure extraction.
    """

    def __init__(self) -> None:
        self._log = get_logger("parser.asura")

    # -- Series metadata -------------------------------------------------------

    def extract_series_title(self, response: Any) -> str:
        """Extract the series title from the page.

        Strategy: Use the <title> tag and strip the ' - Asura Scans' suffix.
        Falls back to heading-based extraction.
        """
        title_els = response.css("title")
        if title_els:
            raw_title = title_els[0].text.strip() if title_els[0].text else ""
            for suffix in (" - Asura Scans", " | Asura Scans"):
                if raw_title.endswith(suffix):
                    raw_title = raw_title[: -len(suffix)].strip()
            if raw_title and raw_title.lower() not in ("asura scans", ""):
                return raw_title

        skip_texts = {
            "", "READ ON OURNEW BETA SITE!", "Asura Scans",
            "Manhwa", "Manga", "Manhua", "Popular",
        }
        for selector in ["h1", "h3", "h2"]:
            elements = response.css(selector)
            for el in elements:
                text = el.text.strip() if el.text else ""
                if text and text not in skip_texts:
                    return text
        raise ParseError("Could not find series title")

    def extract_synopsis(self, response: Any) -> str | None:
        """Extract the synopsis text from the series page."""
        synopsis_parts: list[str] = []
        found_synopsis_heading = False

        all_h3 = response.css("h3")
        for h3 in all_h3:
            text = (h3.text or "").strip()
            if text.lower().startswith("synopsis"):
                found_synopsis_heading = True
                break

        if found_synopsis_heading:
            skip_indicators = (
                "read ", "download ", "english", "eng,",
                "manga scan", "high quality", "keywords",
                "toraka", "track all",
            )
            spans = response.css("span")
            for span in spans:
                text = (span.text or "").strip()
                cls = span.attrib.get("class", "")
                if not text or len(text) < 20:
                    continue
                text_lower = text.lower()
                if any(kw in text_lower for kw in skip_indicators):
                    continue
                if "font-bold" in cls or "text-xs" in cls:
                    continue
                synopsis_parts.append(text)

        if synopsis_parts:
            return " ".join(synopsis_parts)
        return None

    def extract_cover_url(self, response: Any) -> str | None:
        """Extract the series cover image URL."""
        images = response.css("img[src]")
        for img in images:
            src = img.attrib.get("src", "")
            if CDN_DOMAIN in src:
                return abs_url(src)
        return None

    def extract_status(self, response: Any) -> str | None:
        """Extract series status (Ongoing, Completed, etc.)."""
        badges = response.css("span[class*=status]")
        for badge in badges:
            text = (badge.text or "").strip()
            if text:
                return text.capitalize()
        return self.extract_labeled_field(response, "Status")

    def extract_labeled_field(self, response: Any, label: str) -> str | None:
        """Extract a field value from an h3 label/value pair."""
        all_h3 = response.css("h3")
        for i, h3 in enumerate(all_h3):
            text = (h3.text or "").strip()
            if text == label and i + 1 < len(all_h3):
                value = (all_h3[i + 1].text or "").strip()
                if value and value not in ("_", "-", "N/A", ""):
                    return value
        return None

    def extract_genres(self, response: Any) -> list[str]:
        """Extract genre tags from genre filter links."""
        genres: list[str] = []
        seen: set[str] = set()
        links = response.css("a[href*=genres]")
        for link in links:
            text = (link.text or "").strip().rstrip(",").strip()
            if text and text not in seen:
                seen.add(text)
                genres.append(text)
        return genres

    def extract_rating(self, response: Any) -> float | None:
        """Extract the series rating score."""
        spans = response.css("span")
        for span in spans:
            cls = span.attrib.get("class", "")
            if "ml-1" in cls and "text-xs" in cls:
                text = (span.text or "").strip()
                try:
                    return float(text)
                except ValueError:
                    continue
        return None

    # -- Chapter list ----------------------------------------------------------

    def extract_chapter_list(
        self,
        response: Any,
        series_title: str,
        series_url: str,
    ) -> list[dict[str, Any]]:
        """Extract all chapter links from the series page."""
        candidates: dict[float, dict[str, Any]] = {}

        all_links = response.css("a[href*=chapter]")
        for link in all_links:
            href = link.attrib.get("href", "")

            if href.startswith("http"):
                abs_href = href
            else:
                abs_href = abs_url(href)

            if "/chapter/" in abs_href and "/series/" not in abs_href:
                parsed = urlparse(abs_href)
                fixed_path = f"/series{parsed.path}"
                abs_href = parsed._replace(path=fixed_path).geturl()

            if "/chapter/" not in abs_href:
                continue

            try:
                chapter_num = parse_chapter_number(abs_href)
            except ParseError:
                continue

            date_published = None
            chapter_title = None
            inner_h3s = link.css("h3")
            for ih in inner_h3s:
                ih_text = (ih.text or "").strip()
                ih_cls = ih.attrib.get("class", "")
                if "text-xs" in ih_cls and ih_text:
                    date_published = parse_asura_date(ih_text)
                elif "text-sm" in ih_cls and ih_text:
                    chapter_title = ih_text

            if not date_published:
                link_text = (link.text or "").strip()
                date_published = self._extract_date_from_text(link_text)

            entry = {
                "series_title": series_title,
                "number": chapter_num,
                "title": chapter_title,
                "url": abs_href,
                "date_published": date_published.isoformat() if date_published else None,
                "page_count": None,
            }

            if chapter_num not in candidates:
                candidates[chapter_num] = entry
            elif date_published and not candidates[chapter_num].get("date_published"):
                candidates[chapter_num] = entry

        chapters = sorted(candidates.values(), key=lambda c: c["number"])
        self._log.debug("chapters_extracted", count=len(chapters))
        return chapters

    @staticmethod
    def _extract_date_from_text(text: str) -> datetime | None:
        """Try to extract a publication date from chapter link text."""
        match = _MONTH_PATTERN.search(text)
        if match:
            return parse_asura_date(match.group(0))
        return None

    # -- Chapter page images ---------------------------------------------------

    def extract_page_images(
        self,
        response: Any,
        series_title: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Extract comic page images from a rendered chapter page."""
        pages: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        page_number = 1

        images = response.css("img[src]")
        for img in images:
            src = img.attrib.get("src", "")
            if not src:
                continue

            abs_src = abs_url(src)

            if CDN_DOMAIN not in abs_src:
                continue

            if any(skip in abs_src for skip in ("thumb", "icon", "avatar", "logo")):
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

    # -- Search / browse -------------------------------------------------------

    def extract_series_links(self, response: Any) -> list[dict[str, Any]]:
        """Extract series title + URL from a search/browse page."""
        results: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        all_links = response.css("a[href]")
        for link in all_links:
            href = link.attrib.get("href", "")
            abs_href = abs_url(href)
            parsed = urlparse(abs_href)

            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) != 2 or parts[0] != "series":
                continue

            slug = parts[1]
            if slug in ("page", "") or "?" in slug:
                continue
            if slug in seen_slugs:
                continue

            seen_slugs.add(slug)
            title = link.text.strip() if link.text else slug
            results.append({
                "title": title,
                "url": abs_href,
            })

        self._log.debug("series_links_extracted", count=len(results))
        return results

    def extract_series_cards(self, response: Any) -> list[dict[str, Any]]:
        """Extract rich card data from the search/browse listing page."""
        results: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        all_links = response.css("a[href]")
        for link in all_links:
            href = link.attrib.get("href", "")
            abs_href = abs_url(href)
            parsed = urlparse(abs_href)

            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) != 2 or parts[0] != "series":
                continue

            slug = parts[1]
            if slug in ("page", "") or "?" in slug:
                continue
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # -- Title
            title = slug
            title_spans = link.css("span")
            # Strategy 0: span with 'block' class + 'font-bold' (most precise)
            for span in title_spans:
                cls = span.attrib.get("class", "")
                if "block" in cls and ("font-bold" in cls or "font-semibold" in cls):
                    text = (span.text or "").strip()
                    if text and text.lower() not in _TYPE_LABELS:
                        title = text
                        break
            # Strategy 1: any bold span, skip type labels
            if title == slug:
                for span in title_spans:
                    cls = span.attrib.get("class", "")
                    if "font-bold" in cls or "font-semibold" in cls:
                        text = (span.text or "").strip()
                        if text and text.lower() not in _TYPE_LABELS:
                            title = text
                            break
            # Strategy 2: h3 inside the card link
            if title == slug:
                for h3 in link.css("h3"):
                    text = (h3.text or "").strip()
                    if text and text.lower() not in _TYPE_LABELS:
                        title = text
                        break
            # Strategy 3: img alt text
            if title == slug:
                for img in link.css("img[alt]"):
                    alt = (img.attrib.get("alt") or "").strip()
                    if alt and alt.lower() not in _TYPE_LABELS:
                        title = alt
                        break

            # -- Latest chapter
            latest_chapter: float | None = None
            for span in title_spans:
                text = (span.text or "").strip()
                cls = span.attrib.get("class", "")
                if text.lower().startswith("chapter") and "font-bold" not in cls:
                    ch_match = re.search(r"(\d+(?:\.\d+)?)", text)
                    if ch_match:
                        latest_chapter = float(ch_match.group(1))
                    break

            # -- Cover image
            cover_url: str | None = None
            images = link.css("img[src]")
            for img in images:
                src = img.attrib.get("src", "")
                if src:
                    cover_url = abs_url(src)
                    break

            # -- Status badge
            status: str | None = None
            status_spans = link.css("span[class*=status]")
            for badge in status_spans:
                text = (badge.text or "").strip()
                if text:
                    status = text.capitalize()
                    break

            # -- Rating
            rating: float | None = None
            for span in title_spans:
                text = (span.text or "").strip()
                try:
                    val = float(text)
                    if 0 <= val <= 10:
                        rating = val
                except ValueError:
                    continue

            results.append({
                "title": title,
                "slug": slug,
                "url": abs_href,
                "latest_chapter": latest_chapter,
                "cover_url": cover_url,
                "status": status,
                "rating": rating,
            })

        self._log.debug("series_cards_extracted", count=len(results))
        return results

    # -- Trending / Popular ---------------------------------------------------

    def extract_popular_today(self, response: Any) -> list[dict[str, Any]]:
        """Extract the 'Popular Today' comic cards from the homepage.

        The homepage has a section headed by an element containing "Popular Today"
        followed by a grid of ``a[href*='/series/']`` cards.

        Returns:
            List of dicts with rank=None, title, slug, url, cover_url,
            latest_chapter, rating.
        """
        results: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        all_links = response.css("a[href]")
        for link in all_links:
            href = link.attrib.get("href", "")
            abs_href = abs_url(href)
            parsed = urlparse(abs_href)

            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) != 2 or parts[0] != "series":
                continue
            slug = parts[1]
            if slug in ("page", "") or "?" in slug:
                continue
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Title — span with 'block' class (most precise)
            title = slug
            all_spans = link.css("span")
            for span in all_spans:
                cls = span.attrib.get("class", "")
                if "block" in cls and ("font-bold" in cls or "font-semibold" in cls):
                    text = (span.text or "").strip()
                    if text and text.lower() not in _TYPE_LABELS:
                        title = text
                        break
            # Fallback: any bold/semibold span, skip type labels
            if title == slug:
                for span in all_spans:
                    cls = span.attrib.get("class", "")
                    if "font-bold" in cls or "font-semibold" in cls:
                        text = (span.text or "").strip()
                        if text and text.lower() not in _TYPE_LABELS:
                            title = text
                            break
            # Fallback: h3 inside the card link
            if title == slug:
                for h3 in link.css("h3"):
                    text = (h3.text or "").strip()
                    if text and text.lower() not in _TYPE_LABELS:
                        title = text
                        break
            # Fallback: img alt text
            if title == slug:
                for img in link.css("img[alt]"):
                    alt = (img.attrib.get("alt") or "").strip()
                    if alt and alt.lower() not in _TYPE_LABELS:
                        title = alt
                        break

            # Latest chapter
            latest_chapter: float | None = None
            for span in link.css("span"):
                text = (span.text or "").strip()
                cls = span.attrib.get("class", "")
                if text.lower().startswith("chapter") and "font-bold" not in cls:
                    ch_match = re.search(r"(\d+(?:\.\d+)?)", text)
                    if ch_match:
                        latest_chapter = float(ch_match.group(1))
                    break

            # Cover
            cover_url: str | None = None
            for img in link.css("img[src]"):
                src = img.attrib.get("src", "")
                if src:
                    cover_url = abs_url(src)
                    break

            # Rating
            rating: float | None = None
            for span in link.css("span"):
                try:
                    val = float((span.text or "").strip())
                    if 0 < val <= 10:
                        rating = val
                except ValueError:
                    continue

            results.append({
                "rank": None,
                "title": title,
                "slug": slug,
                "url": abs_href,
                "cover_url": cover_url,
                "genres": [],
                "rating": rating,
                "latest_chapter": latest_chapter,
                "view_count": None,
            })

        self._log.debug("popular_today_extracted", count=len(results))
        return results

    def extract_popular_ranked(self, response: Any) -> list[dict[str, Any]]:
        """Extract the ranked 'Popular' sidebar items from the homepage.

        The sidebar shows comics ranked #1–10. Each item contains a rank
        number in a bordered div, a cover image, a ``<h3>`` title, genres,
        and a rating score.

        Returns:
            List of dicts sorted ascending by rank.
        """
        results: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        all_links = response.css("a[href]")
        for link in all_links:
            href = link.attrib.get("href", "")
            abs_href = abs_url(href)
            parsed = urlparse(abs_href)

            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) != 2 or parts[0] != "series":
                continue
            slug = parts[1]
            if slug in ("page", "") or "?" in slug:
                continue
            if slug in seen_slugs:
                continue

            # Rank number lives in a bordered box div up to 4 ancestors up
            rank: int | None = None
            node = link.parent
            for _ in range(4):
                if node is None:
                    break
                for div in node.css("div"):
                    cls = div.attrib.get("class", "")
                    if "border-white" in cls and "border-[1px]" in cls:
                        try:
                            rank = int((div.text or "").strip())
                        except ValueError:
                            pass
                        break
                if rank is not None:
                    break
                node = node.parent

            if rank is None:
                continue  # not a sidebar ranked item

            seen_slugs.add(slug)

            # Title from h3 inside link
            title = slug
            for h3 in link.css("h3"):
                text = (h3.text or "").strip()
                if text:
                    title = text
                    break
            # Fallback: bold/semibold span
            if title == slug:
                for span in link.css("span"):
                    cls = span.attrib.get("class", "")
                    if "font-bold" in cls or "font-semibold" in cls:
                        text = (span.text or "").strip()
                        if text:
                            title = text
                            break
            # Fallback: img alt text
            if title == slug:
                for img in link.css("img[alt]"):
                    alt = (img.attrib.get("alt") or "").strip()
                    if alt:
                        title = alt
                        break

            # Cover
            cover_url: str | None = None
            for img in link.css("img[src]"):
                src = img.attrib.get("src", "")
                if src:
                    cover_url = abs_url(src)
                    break

            # Genres — comma-separated title-cased text span
            genres: list[str] = []
            for span in link.css("span"):
                text = (span.text or "").strip()
                if "," in text:
                    candidates = [g.strip().rstrip(",") for g in text.split(",")]
                    genres = [g for g in candidates if g and g[0].isupper()]
                    if genres:
                        break

            # Rating
            rating: float | None = None
            for span in link.css("span"):
                try:
                    val = float((span.text or "").strip())
                    if 0 < val <= 10:
                        rating = val
                except ValueError:
                    continue

            results.append({
                "rank": rank,
                "title": title,
                "slug": slug,
                "url": abs_href,
                "cover_url": cover_url,
                "genres": genres,
                "rating": rating,
                "latest_chapter": None,
                "view_count": None,
            })

        results.sort(key=lambda x: x["rank"] or 999)
        self._log.debug("popular_ranked_extracted", count=len(results))
        return results

    # -- Chapter title from chapter page (Phase 3) -----------------------------


    def extract_title_from_chapter_page(self, response: Any) -> str:
        """Extract the series title from a chapter page's <title> tag.

        Chapter pages have titles like "Series Title Chapter N - Asura Scans".
        """
        title_els = response.css("title")
        if title_els:
            raw = (title_els[0].text or "").strip()
            for suffix in (" - Asura Scans", " | Asura Scans"):
                if raw.endswith(suffix):
                    raw = raw[: -len(suffix)].strip()
            # Remove "Chapter N" suffix
            raw = re.sub(r"\s+Chapter\s+\d+(?:\.\d+)?$", "", raw).strip()
            if raw:
                return raw
        raise ParseError("Could not extract series title from chapter page")
