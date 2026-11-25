import asyncio
import base64
import inspect
from pathlib import Path

from fastmcp import FastMCP
from flaticon import FlatIconClient
from mcp.types import ImageContent, TextContent

mcp = FastMCP("Flaticon Icons")

# Default folder the flaticon library downloads into (same as your test script)
DEFAULT_DIR = Path.home() / "flaticon"
MAX_COUNT = 10

# download dir is shared, so handle one request at a time to avoid mixing files
_lock = asyncio.Lock()


@mcp.tool
async def search_icons(query: str, count: int = 3) -> list:
    """Search Flaticon and return PNG icons/stickers as images.

    Args:
        query: What the icon should show, e.g. "airport", "happy person", "coffee".
        count: Number of PNG images wanted (1-10).
    """
    count = max(1, min(int(count), MAX_COUNT))
    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)

    async with _lock:
        before = set(DEFAULT_DIR.glob("*.png"))

        async with FlatIconClient() as client:
            res = client.search_for_images(query, count=count)
            images = await res if inspect.isawaitable(res) else res
            for img in images:
                dl = client.download_image(img)
                if inspect.isawaitable(dl):
                    await dl

        new_files = sorted(set(DEFAULT_DIR.glob("*.png")) - before)

        results = []
        for f in new_files[:count]:
            data = f.read_bytes()
            results.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(data).decode(),
                    mimeType="image/png",
                )
            )
            f.unlink(missing_ok=True)  # keep server disk clean

    if not results:
        return [TextContent(type="text", text=f"No icons found for '{query}'.")]

    results.insert(0, TextContent(type="text", text=f"{len(results)} PNG icons for '{query}':"))
    return results


if __name__ == "__main__":
    mcp.run()