"""MangaKakalot HTML parser — extract comic data from server-rendered pages.

Handles both mangakakalot.gg and manganato.gg URLs since they are
sister sites with identical DOM structures.

.. note::

   The original domains (mangakakalot.com, chapmanganato.to) went offline
   in early 2025.  This module now targets the replacement ``.gg`` domains.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from comic_crawler.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANGAKAKALOT_BASE = "https://www.manganato.gg"
MANGANATO_BASE = "https://www.manganato.gg"

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class MangaKakalotPageParser:
    """Parse manga data from MangaKakalot / Manganato HTML pages.

    The new ``.gg`` sites use a "MangaBox"-style template with
    consistent CSS selectors across search, detail, and reader pages.
    """

    # -- Search results ----------------------------------------------------

    def extract_search_cards(
        self,
        response: Any,
        base_url: str = MANGAKAKALOT_BASE,
    ) -> list[dict[str, Any]]:
        """Extract search result cards from the listing page.

        Works with both MangaKakalot and Manganato search/browse results.
        The new site uses ``.story_item`` for search results.
        """
        cards: list[dict[str, Any]] = []

        # New manganato.gg: .list-comic-item-wrap
        items = response.css(".list-comic-item-wrap")
        if not items:
            # Fallback: mangakakalot.gg used .story_item
            items = response.css(".story_item")
        if not items:
            # Fallback: some browse/genre pages may use a different class
            items = response.css(".list-story-item")

        for item in items:
            try:
                # Title and URL — prefer h3 > a, fallback to .story_name a
                link = item.css("h3 a") or item.css(".story_item_right h3 a") or item.css(".story_name a")
                if not link:
                    # Last resort: first <a> with a title attr
                    link = item.css("a[title]")
                if not link:
                    continue

                first_link = link[0]
                title = first_link.attrib.get("title", "") or first_link.text or ""
                url = first_link.attrib.get("href", "")
                title = title.strip()

                if not url or not title:
                    continue

                # Make URL absolute
                if not url.startswith("http"):
                    url = urljoin(base_url, url)

                # Extract slug
                slug = self._slug_from_url(url)

                # Cover image
                img = item.css("img")
                cover_url = None
                if img:
                    cover_url = (
                        img[0].attrib.get("src", "")
                        or img[0].attrib.get("data-src", "")
                    )

                # Latest chapter
                latest_chapter = None
                ch_links = (
                    item.css("em a")
                    or item.css(".story_chapter a")
                    or item.css("a[href*='chapter']")
                )
                if ch_links:
                    ch_text = ch_links[0].text or ch_links[0].attrib.get("title", "")
                    ch_match = re.search(
                        r"chapter[_\s-]*([\d]+(?:\.[\d]+)?)",
                        ch_text,
                        re.IGNORECASE,
                    )
                    if ch_match:
                        latest_chapter = float(ch_match.group(1))

                cards.append({
                    "title": title,
                    "slug": slug,
                    "url": url,
                    "cover_url": cover_url,
                    "latest_chapter": latest_chapter,
                    "status": None,
                    "rating": None,
                })
            except Exception:
                log.warning("search_card_parse_error", exc_info=True)
                continue

        return cards

    def extract_has_next_page(self, response: Any) -> bool:
        """Check if there's a next page link in pagination."""
        # New site: .panel_page_number with page links
        next_links = (
            response.css("a.page_last")
            or response.css("a.page-next")
            or response.css(".panel_page_number a.page_blue.page_last")
        )
        return bool(next_links)

    # -- Series detail -----------------------------------------------------

    def extract_series_title(self, response: Any) -> str:
        """Extract series title from detail page."""
        # New .gg site: .manga-info-text h1
        h1 = (
            response.css(".manga-info-text h1")
            or response.css(".story-info-right h1")
        )
        if h1:
            return (h1[0].text or "").strip()
        return "Unknown"

    def extract_cover_url(self, response: Any) -> str | None:
        """Extract cover image URL."""
        img = (
            response.css(".manga-info-pic img")
            or response.css(".info-image img")
        )
        if img:
            return img[0].attrib.get("src") or img[0].attrib.get("data-src")
        return None

    def extract_synopsis(self, response: Any) -> str:
        """Extract series description/synopsis."""
        # New .gg site uses #contentBox
        desc = (
            response.css("#contentBox")
            or response.css("#panel-story-info-description")
            or response.css("#noidungm")
        )
        if desc:
            text = desc[0].text or ""
            # Clean "Description :" prefix
            text = re.sub(r"^Description\s*:\s*", "", text, flags=re.IGNORECASE)
            return text.strip()
        return ""

    def extract_author(self, response: Any) -> str:
        """Extract author name."""
        # Look in info text list items
        rows = (
            response.css(".manga-info-text li")
            or response.css(".variations-tableInfo tr")
        )
        for row in rows:
            label = (row.text or "").lower()
            if "author" in label:
                links = row.css("a")
                if links:
                    return (links[0].text or "").strip()
                # No link — extract text after "Author(s) :"
                match = re.search(r"author\(?s?\)?\s*:\s*(.+)", label, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return ""

    def extract_genres(self, response: Any) -> list[str]:
        """Extract genre list."""
        genres: list[str] = []

        # Try .manga-info-text li with genre links
        rows = (
            response.css(".manga-info-text li")
            or response.css(".variations-tableInfo tr")
        )
        for row in rows:
            label = (row.text or "").lower()
            if "genre" in label:
                for link in row.css("a"):
                    name = (link.text or "").strip()
                    if name:
                        genres.append(name)
                break
        return genres

    def extract_status(self, response: Any) -> str | None:
        """Extract publication status."""
        rows = (
            response.css(".manga-info-text li")
            or response.css(".variations-tableInfo tr")
        )
        for row in rows:
            label = (row.text or "").lower()
            if "status" in label:
                if "ongoing" in label:
                    return "Ongoing"
                if "completed" in label or "complete" in label:
                    return "Completed"
        return None

    # -- Chapter list ------------------------------------------------------

    def extract_chapter_list(
        self,
        response: Any,
        series_title: str,
    ) -> list[dict[str, Any]]:
        """Extract the chapter list from a series detail page."""
        chapters: list[dict[str, Any]] = []

        # New .gg site: .chapter-list .row
        items = (
            response.css(".chapter-list .row")
            or response.css(".row-content-chapter li")
        )

        for item in items:
            try:
                link = item.css("a")
                if not link:
                    continue
                first_link = link[0]

                ch_url = first_link.attrib.get("href", "")
                ch_title = (first_link.text or "").strip()

                # Parse chapter number from URL or title
                ch_match = re.search(
                    r"chapter[_\s-]*([\d]+(?:\.[\d]+)?)", ch_url, re.IGNORECASE
                )
                if not ch_match:
                    ch_match = re.search(
                        r"chapter[_\s-]*([\d]+(?:\.[\d]+)?)", ch_title, re.IGNORECASE
                    )
                number = float(ch_match.group(1)) if ch_match else 0.0

                # Date — last span in the row
                spans = item.css("span")
                date_str = None
                if len(spans) >= 2:
                    date_str = (spans[-1].text or "").strip()
                if not date_str:
                    date_el = item.css(".chapter-time") or item.css("span[title]")
                    if date_el:
                        date_str = date_el[0].attrib.get("title") or (
                            date_el[0].text or ""
                        ).strip()

                chapters.append({
                    "series_title": series_title,
                    "number": number,
                    "title": ch_title or f"Chapter {number}",
                    "url": ch_url,
                    "date_published": date_str,
                    "page_count": None,
                })
            except Exception:
                log.warning("chapter_parse_error", exc_info=True)
                continue

        return chapters

    # -- Chapter pages (images) --------------------------------------------

    def extract_page_images(
        self,
        response: Any,
        series_title: str,
        chapter_number: float,
    ) -> list[dict[str, Any]]:
        """Extract page image URLs from a chapter reader page."""
        pages: list[dict[str, Any]] = []

        # Both old and new sites: .container-chapter-reader img
        images = response.css(".container-chapter-reader img")

        for idx, img in enumerate(images, start=1):
            src = (
                img.attrib.get("src", "")
                or img.attrib.get("data-src", "")
            )
            if not src or "logo" in src.lower() or "ads" in src.lower():
                continue

            pages.append({
                "series_title": series_title,
                "chapter_number": chapter_number,
                "page_number": idx,
                "image_url": src.strip(),
            })

        return pages

    def extract_title_from_chapter_page(self, response: Any) -> str:
        """Extract the series title from a chapter reader page."""
        # New site: .info-top-chapter h2
        info = response.css(".info-top-chapter h2")
        if info:
            text = (info[0].text or "").strip()
            # "One Piece Chapter 1175" → "One Piece"
            cleaned = re.sub(r"\s*chapter\s*[\d.]+.*$", "", text, flags=re.IGNORECASE)
            if cleaned:
                return cleaned.strip()

        # Fallback: breadcrumb
        breadcrumb = response.css(".panel-breadcrumb a") or response.css(
            ".breadcrumb a"
        )
        if len(breadcrumb) >= 2:
            return (breadcrumb[1].text or "").strip()

        # Fallback to title tag
        title = response.css("title")
        if title:
            t = (title[0].text or "").strip()
            # "Title - Chapter X" → "Title"
            return t.split(" - ")[0].strip()
        return "Unknown"

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _slug_from_url(url: str) -> str:
        """Extract slug from a MangaKakalot/Manganato URL.

        New .gg site examples:
            https://www.mangakakalot.gg/manga/one-piece → one-piece
            https://www.manganato.gg/manga/one-piece → one-piece
        """
        path = url.rstrip("/").split("/")[-1]
        return path
