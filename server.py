import base64
import shutil
import uuid
from pathlib import Path

from fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from flaticon import FlatIconClient  # vendored copy in ./flaticon

mcp = FastMCP("Flaticon Icons")

MAX_COUNT = 10


@mcp.tool
async def search_icons(query: str, count: int = 3) -> list:
    """Search Flaticon and return PNG icons/stickers as images.

    Args:
        query: What the icon should show, e.g. "airport", "happy person", "coffee".
        count: Number of PNG images wanted (1-10).
    """
    count = max(1, min(int(count), MAX_COUNT))

    # unique temp folder per request (under the home dir, as the library expects)
    rel = f"flaticon_tmp/{uuid.uuid4().hex}"
    tmp_dir = Path.home() / rel

    try:
        async with FlatIconClient(relative_path=rel) as client:
            found = await client.search_for_images(query, count=count)

            paths, captions, seen = [], [], set()
            for img in found:
                p = await client.download_image(img)
                if p in seen or not p.exists() or p.stat().st_size == 0:
                    continue
                seen.add(p)
                paths.append(p)
                captions.append(f"{len(paths)}. {img.name} (pack: {img.pack})")

        if not paths:
            return [TextContent(type="text", text=f"No icons found for '{query}'.")]

        out = [TextContent(type="text", text=f"{len(paths)} PNG icons for '{query}':\n" + "\n".join(captions))]
        for p in paths:
            out.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(p.read_bytes()).decode(),
                    mimeType="image/png",
                )
            )
        return out

    except Exception as e:
        return [TextContent(type="text", text=f"Icon search failed: {type(e).__name__}: {e}")]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    mcp.run()
