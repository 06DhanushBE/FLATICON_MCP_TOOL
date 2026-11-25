# Vendored from flaticon==1.0.2 (Apache-2.0), with small fixes:
#  - URL-encode the query and use order_by.value
#  - send a browser User-Agent
#  - read the page with response.text()
from __future__ import annotations

from os import makedirs
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from .models import Image, OrderBy, Shape
from .utils import download

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class FlatIconClient:
    datapath: Path

    _session: ClientSession
    _csv_file: Path

    def __init__(self, relative_path: str = "flaticon") -> None:
        self.datapath = Path.home() / relative_path
        self._csv_file = self.datapath / "images.csv"

        makedirs(self.datapath, exist_ok=True)
        if not self._csv_file.exists():
            self._csv_file.touch()
            self._csv_file.write_text(",".join(Image.__annotations__))

    async def __aenter__(self):
        self._session = ClientSession(headers=HEADERS)
        return self

    async def __aexit__(self, *args: Any):
        await self._session.close()

    async def search_for_images(
        self,
        query: str,
        shape: Shape = Shape.ALL_SHAPES,
        order_by: OrderBy = OrderBy.POPULER,
        count: int = 10,
    ) -> list[Image]:
        url = f"https://www.flaticon.com/search?word={quote_plus(query)}"
        if shape != Shape.ALL_SHAPES:
            url += f"&shape={shape.value}"
        url += f"&order_by={order_by.value}"

        images: list[Image] = []
        async with self._session.get(url) as page:
            page.raise_for_status()
            soup = BeautifulSoup(await page.text(), "html.parser")
            results = soup.find_all("li", class_="icon--item")
            for result in results[:count]:
                try:
                    images.append(
                        Image(
                            id=result["data-png"].split("?")[0].split("/")[-1].split(".")[0],
                            name=result["data-name"],
                            url=result["data-png"],
                            downloads=result.get("data-downloads", 0),
                            pack=result.get("data-pack_name", "Unknown"),
                        )
                    )
                except Exception:  # ads / malformed items
                    pass
        return images

    async def download_image(self, image: Image) -> Path:
        imagepath = self.datapath / f"{image.id}.png"
        with self._csv_file.open("r") as csv_file:
            for line in csv_file.readlines():
                if str(image.id) in line.split(",")[0]:
                    return imagepath
        await download(image.url, imagepath, self._session)
        with self._csv_file.open("a") as file:
            file.write("\n" + ",".join(map(str, image.to_dict().values())))
        return imagepath
