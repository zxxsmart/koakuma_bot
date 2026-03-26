from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.request import urlopen


async def download_image(image_url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _download() -> Path:
        with urlopen(image_url) as response:
            output_path.write_bytes(response.read())
        return output_path

    return await asyncio.to_thread(_download)
