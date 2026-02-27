from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


def _search_pexels(
    query: str,
    per_page: int,
    api_key: str,
    timeout_sec: int,
) -> list[dict[str, Any]]:
    params = urlencode({"query": query, "per_page": per_page, "page": 1})
    request = Request(
        f"{PEXELS_SEARCH_URL}?{params}",
        headers={"Authorization": api_key},
        method="GET",
    )
    with urlopen(request, timeout=timeout_sec) as response:
        payload = json.loads(response.read().decode("utf-8"))
    photos = payload.get("photos")
    if not isinstance(photos, list):
        return []
    return [item for item in photos if isinstance(item, dict)]


def _pick_image_url(photo: dict[str, Any]) -> str | None:
    src = photo.get("src")
    if not isinstance(src, dict):
        return None
    for key in ("large2x", "large", "original"):
        value = src.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _download_bytes(url: str, timeout_sec: int) -> bytes:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout_sec) as response:
        return response.read()


def _next_file_path(destination_dir: Path, base_name: str, ext: str) -> Path:
    index = 1
    while True:
        candidate = destination_dir / f"{base_name}_{index}{ext}"
        if not candidate.exists():
            return candidate
        index += 1


def _fetch_topic_images_sync(
    *,
    topic: str,
    limit: int,
    destination_dir: Path,
    min_width: int,
    min_height: int,
    api_key: str,
    timeout_sec: int,
) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    photos = _search_pexels(topic, per_page=min(max(limit * 3, 10), 80), api_key=api_key, timeout_sec=timeout_sec)
    output: list[Path] = []

    for photo in photos:
        if len(output) >= limit:
            break
        image_url = _pick_image_url(photo)
        if not image_url:
            continue
        try:
            payload = _download_bytes(image_url, timeout_sec=timeout_sec)
            with Image.open(io.BytesIO(payload)) as img:
                width, height = img.size
                if width < min_width or height < min_height:
                    continue
                image_format = (img.format or "JPEG").upper()
                ext = ".png" if image_format == "PNG" else ".jpg"
                output_path = _next_file_path(destination_dir, "auto_topic_image", ext)
                img.convert("RGB").save(output_path, format="JPEG" if ext == ".jpg" else "PNG")
                output.append(output_path)
        except Exception:
            continue
    return output


async def fetch_topic_images(
    *,
    topic: str,
    limit: int,
    destination_dir: Path,
    min_width: int,
    min_height: int,
    api_key: str,
    timeout_sec: int = 15,
) -> list[Path]:
    if limit <= 0 or not topic.strip() or not api_key.strip():
        return []
    return await asyncio.to_thread(
        _fetch_topic_images_sync,
        topic=topic.strip(),
        limit=limit,
        destination_dir=destination_dir,
        min_width=min_width,
        min_height=min_height,
        api_key=api_key.strip(),
        timeout_sec=max(5, timeout_sec),
    )
