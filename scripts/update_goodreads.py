#!/usr/bin/env python3
"""Rebuild the bookshelf cover cells in index.html from the Goodreads RSS feed.

Fetches the "read" shelf RSS (most-recently-read first) and splices a set of
<a><img></a> cover cells into index.html between the GOODREADS-START /
GOODREADS-END markers. The surrounding .shelf wrapper and styling live in the
HTML; this only regenerates the cells. Exits non-zero on a fetch/parse failure
so a transient outage leaves the committed page untouched.
"""

import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_ID = "13717595"
SHELF = "read"
FEED_URL = (
    f"https://www.goodreads.com/review/list_rss/{USER_ID}"
    f"?shelf={SHELF}&sort=date_read"
)
MAX_BOOKS = 24

PAGE = Path(__file__).resolve().parent.parent / "index.html"
START = "<!-- GOODREADS-START -->"
END = "<!-- GOODREADS-END -->"


def fetch_feed() -> bytes:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def parse_books(raw: bytes):
    root = ET.fromstring(raw)
    books = []
    for item in root.iterfind(".//item"):
        book_id = text(item, "book_id")
        title = text(item, "title")
        cover = (
            text(item, "book_large_image_url")
            or text(item, "book_medium_image_url")
            or text(item, "book_image_url")
        )
        if not (book_id and title and cover):
            continue
        books.append(
            {
                "title": title,
                "cover": cover,
                "url": f"https://www.goodreads.com/book/show/{book_id}",
            }
        )
        if len(books) >= MAX_BOOKS:
            break
    return books


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_cells(books) -> str:
    if not books:
        return "      <!-- no books found -->"
    lines = []
    for b in books:
        t = esc(b["title"])
        lines.append(
            f'      <a href="{b["url"]}" target="_blank" rel="noopener" title="{t}">'
            f'<img src="{b["cover"]}" loading="lazy" alt="{t}"></a>'
        )
    return "\n".join(lines)


def splice(page_text: str, cells: str) -> str:
    block = f"{START}\n{cells}\n      {END}"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(page_text):
        raise SystemExit("markers not found in index.html")
    return pattern.sub(lambda _: block, page_text)


def main() -> int:
    try:
        raw = fetch_feed()
        books = parse_books(raw)
    except Exception as exc:  # leave the page untouched on any failure
        print(f"goodreads update failed: {exc}", file=sys.stderr)
        return 1
    cells = build_cells(books)
    original = PAGE.read_text(encoding="utf-8")
    updated = splice(original, cells)
    if updated != original:
        PAGE.write_text(updated, encoding="utf-8")
        print(f"updated bookshelf with {len(books)} books")
    else:
        print("no change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
