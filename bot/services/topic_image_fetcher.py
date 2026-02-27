from __future__ import annotations

import asyncio
import io
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image
from openai import AsyncOpenAI

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
HTTP_HEADERS = {
    "User-Agent": "LibraScorpBot/1.0 (+https://pexels.com)",
    "Accept": "application/json",
}
logger = logging.getLogger(__name__)


def _search_pexels(
    query: str,
    per_page: int,
    api_key: str,
    timeout_sec: int,
) -> list[dict[str, Any]]:
    params = urlencode({"query": query, "per_page": per_page, "page": 1})
    request = Request(
        f"{PEXELS_SEARCH_URL}?{params}",
        headers={**HTTP_HEADERS, "Authorization": api_key},
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
    request = Request(url, headers=HTTP_HEADERS, method="GET")
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


async def translate_topic_to_russian(
    *,
    topic: str,
    source_lang: str,
    openrouter_api_key: str,
    openrouter_models: tuple[str, ...],
    request_timeout_sec: int,
    max_model_attempts: int,
) -> str:
    normalized_topic = topic.strip()
    if not normalized_topic or source_lang != "uz":
        return normalized_topic
    if not openrouter_api_key.strip() or not openrouter_models:
        return normalized_topic

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_api_key.strip())
    timeout_sec = max(10, int(request_timeout_sec))
    models = openrouter_models[: max(1, int(max_model_attempts))]

    for model in models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Translate Uzbek text into natural Russian. "
                            "Return only the translated text, no notes, no quotes."
                        ),
                    },
                    {"role": "user", "content": normalized_topic[:3000]},
                ],
                temperature=0.0,
                timeout=timeout_sec,
            )
            translated = (response.choices[0].message.content or "").strip()
            if translated:
                return translated
        except Exception as exc:
            logger.warning("Uzbek->Russian topic translation failed (%s): %s", model, exc)

    return normalized_topic
