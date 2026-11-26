import asyncio
import base64
import os
import re
from urllib.parse import quote_plus

import aiohttp
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

mcp = FastMCP("Flaticon Icons")

BASE = os.environ.get("FLATICON_BASE", "https://www.flaticon.com")

DEFAULT_COUNT = 10
MAX_LINES = 10            # lines per call
MAX_PER_LINE = 500        # results per line
MAX_PAGES = 10            # result pages to read per line
PREFER_512 = True         # icons/stickers: 512px PNG (data-png). False = 128px <img src>
INLINE_STATIC = 10        # max PNGs returned as inline images per call
INLINE_ANIMATED = 3       # max GIFs returned as inline images per call
MAX_INLINE_BYTES = 1_500_000

KINDS = {"i": "icon", "s": "sticker", "a": "animated"}
TYPE_PARAM = {"icon": "", "sticker": "&type=sticker", "animated": "&type=animated-icon"}


# ---------------------------------------------------------------- parsing
def parse_requests(text: str):
    """Lines like 'hello,I,20' / 'hello,S,50' / 'hello,A,200' -> (jobs, notes)."""
    jobs, notes = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.lower().startswith("query,"):
            continue
        parts = [p.strip() for p in line.rsplit(",", 2)]
        if len(parts) == 3:
            q, k, n = parts
        elif len(parts) == 2:
            q, k = parts
            n = str(DEFAULT_COUNT)
        else:
            q, k, n = parts[0], "I", str(DEFAULT_COUNT)
        kind = KINDS.get(k[:1].lower())
        if not q or kind is None or not n.isdigit() or int(n) < 1:
            notes.append(f"Could not read line: '{line}' (use: query,I|S|A,number)")
            continue
        jobs.append((q, kind, min(int(n), MAX_PER_LINE)))
    if len(jobs) > MAX_LINES:
        notes.append(f"Only the first {MAX_LINES} lines were used.")
    return jobs[:MAX_LINES], notes


def page_url(word: str, kind: str, page: int) -> str:
    path = "/search" if page == 1 else f"/search/{page}"
    return f"{BASE}{path}?word={quote_plus(word)}{TYPE_PARAM[kind]}"


def total_pages(html: str) -> int:
    span = BeautifulSoup(html, "html.parser").select_one("section.pagination-bar span#pagination-total")
    if span and span.get_text(strip=True).isdigit():
        return int(span.get_text(strip=True))
    return 1  # empty / missing pagination bar -> only this page


def png_to_gif(png_url):
    m = re.search(r"/(?:128|512)/(\d+)/(\d+)\.png", png_url or "")
    return f"https://cdn-icons-gif.flaticon.com/{m.group(1)}/{m.group(2)}.gif" if m else None


def parse_items(html: str, kind: str):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.select("li.icon--item"):
        img = li.select_one("div.icon--holder a img")
        if img is None:
            continue
        if kind == "animated":
            png = None
            srcset = (img.get("srcset") or "").strip()
            if srcset:
                png = srcset.split(",")[0].split()[0]
            png = png or img.get("data-src") or img.get("src")
            url = li.get("data-gif") or png_to_gif(png)
            if not url and (img.get("src") or "").endswith(".gif"):
                url = img.get("src")
        else:
            src = img.get("src") or img.get("data-src")
            url = (li.get("data-png") or src) if PREFER_512 else (src or li.get("data-png"))
        if not url or not url.startswith("http"):
            continue
        items.append({"id": li.get("data-id"), "name": li.get("data-name") or "icon", "url": url})
    return items


# ---------------------------------------------------------------- crawling
async def crawl(session, word: str, kind: str, count: int):
    results, seen = [], set()
    page, total = 1, 1
    while page <= min(total, MAX_PAGES) and len(results) < count:
        async with session.get(page_url(word, kind, page)) as r:
            if r.status != 200:
                if page == 1:
                    raise RuntimeError(f"Flaticon returned HTTP {r.status}")
                break
            html = await r.text()
        if page == 1:
            total = total_pages(html)
        new = [i for i in parse_items(html, kind) if i["url"] not in seen]
        if not new:
            break
        for i in new:
            seen.add(i["url"])
            results.append(i)
        page += 1
        if page <= min(total, MAX_PAGES) and len(results) < count:
            await asyncio.sleep(1)
    return results[:count]


async def fetch_image(session, sem, item, default_type):
    async with sem:
        try:
            async with session.get(item["url"]) as r:
                if r.status == 200:
                    data = await r.read()
                    if len(data) > MAX_INLINE_BYTES:
                        return None, None
                    ctype = r.content_type if (r.content_type or "").startswith("image/") else default_type
                    return data, ctype
        except Exception:
            pass
    return None, None


# ---------------------------------------------------------------- tool
@mcp.tool
async def search_icons(requests: str) -> list:
    """Search Flaticon for PNG icons, PNG stickers and animated GIF icons.

    One request per line, format:

        query,type,number

    type: I = icons, S = stickers, A = animated icons (GIF).
    Example (three requests):

        hello,I,20
        hello,S,50
        hello,A,200

    If fewer results exist than requested, all that exist are returned.
    Returns every result's name and direct link; the first few are also shown
    as inline images (the rest are links, to keep the response small).
    """
    jobs, notes = parse_requests(requests)
    if not jobs:
        return [TextContent(type="text", text="No valid lines. Use: query,I|S|A,number\n" + "\n".join(notes))]

    out = []
    if notes:
        out.append(TextContent(type="text", text="\n".join(notes)))

    left = {"static": INLINE_STATIC, "animated": INLINE_ANIMATED}
    sem = asyncio.Semaphore(5)

    try:
        async with aiohttp.ClientSession() as session:  # plain request, no custom headers
            for n_job, (query, kind, count) in enumerate(jobs):
                if n_job:
                    await asyncio.sleep(1)
                try:
                    items = await crawl(session, query, kind, count)
                except Exception as e:
                    out.append(TextContent(type="text", text=f"'{query}' ({kind}): search failed: {type(e).__name__}: {e}"))
                    continue
                if not items:
                    out.append(TextContent(type="text", text=f"'{query}' ({kind}): no results."))
                    continue

                bucket = "animated" if kind == "animated" else "static"
                shown = items[: left[bucket]]
                left[bucket] -= len(shown)
                default_type = "image/gif" if kind == "animated" else "image/png"
                fetched = await asyncio.gather(*(fetch_image(session, sem, i, default_type) for i in shown))

                note = "" if len(items) >= count else f" (only {len(items)} exist)"
                lines = [f"{n}. {i['name']} | {i['url']}" for n, i in enumerate(items, 1)]
                out.append(TextContent(
                    type="text",
                    text=f"'{query}' ({kind}): returning {len(items)} of {count} requested{note}\n" + "\n".join(lines),
                ))
                for data, ctype in fetched:
                    if data:
                        out.append(ImageContent(type="image", data=base64.b64encode(data).decode(), mimeType=ctype))
    except Exception as e:
        out.append(TextContent(type="text", text=f"Search failed: {type(e).__name__}: {e}"))
    return out


if __name__ == "__main__":
    mcp.run()
