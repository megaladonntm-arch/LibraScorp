from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets_pdf"
OPENROUTER_API_KEY = "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"
MODEL_CANDIDATES = (
    "openai/gpt-oss-120b:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-4o-mini",
)


@dataclass
class SlideContent:
    title: str
    bullets: list[str]


def list_presentation_types() -> list[int]:
    if not ASSETS_DIR.exists():
        return []

    numbers: set[int] = set()
    for file_path in ASSETS_DIR.iterdir():
        if not file_path.is_file():
            continue
        match = re.match(r"^(\d+)", file_path.stem)
        if match:
            numbers.add(int(match.group(1)))
    return sorted(numbers)


def resolve_template_asset(template_type: int) -> Path | None:
    if not ASSETS_DIR.exists():
        return None

    for file_path in ASSETS_DIR.iterdir():
        if not file_path.is_file():
            continue
        match = re.match(r"^(\d+)", file_path.stem)
        if not match:
            continue
        if int(match.group(1)) != template_type:
            continue
        if file_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            return file_path
    return None


def _extract_json(payload: str) -> Any:
    raw = payload.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data.get("slides", []) if isinstance(data, dict) else data
        raise


def _fallback_slides(topic: str, slide_count: int) -> list[SlideContent]:
    slides: list[SlideContent] = []
    for i in range(1, slide_count + 1):
        if i == 1:
            slides.append(
                SlideContent(
                    title=f"{topic}: обзор",
                    bullets=[
                        "Вводная часть по теме.",
                        "Почему это важно сейчас.",
                        "Что разберем в презентации.",
                    ],
                )
            )
        elif i == slide_count:
            slides.append(
                SlideContent(
                    title="Заключение",
                    bullets=[
                        "Ключевые выводы.",
                        "Практические шаги.",
                        "Итоговая рекомендация.",
                    ],
                )
            )
        else:
            slides.append(
                SlideContent(
                    title=f"{topic}: слайд {i}",
                    bullets=[
                        "Главная идея слайда.",
                        "Подтверждающие факты или пример.",
                        "Короткий промежуточный вывод.",
                    ],
                )
            )
    return slides


def _normalize_slides(topic: str, slide_count: int, raw: Any) -> list[SlideContent]:
    if isinstance(raw, dict):
        raw = raw.get("slides")

    if not isinstance(raw, list):
        return _fallback_slides(topic, slide_count)

    slides: list[SlideContent] = []
    for item in raw[:slide_count]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip() or "Без названия"
        bullets_raw = item.get("bullets", [])
        if not isinstance(bullets_raw, list):
            bullets_raw = []
        bullets = [str(x).strip() for x in bullets_raw if str(x).strip()]
        if not bullets:
            bullets = ["Главная мысль слайда."]
        slides.append(SlideContent(title=title, bullets=bullets[:5]))

    if len(slides) < slide_count:
        fallback = _fallback_slides(topic, slide_count)
        slides.extend(fallback[len(slides):slide_count])

    return slides[:slide_count]


def _generate_sync(topic: str, slide_count: int, template_type: int) -> list[SlideContent]:
    api_key = OPENROUTER_API_KEY.strip()
    if not api_key:
        logger.error("OPENROUTER_API_KEY is empty")
        return _fallback_slides(topic, slide_count)

    prompt = (
        "Generate slide content in Russian. Return JSON only.\n"
        f"Topic: {topic}\n"
        f"Slide count: {slide_count}\n"
        f"Template type: {template_type}\n\n"
        "Format:\n"
        "{\n"
        '  "slides": [\n'
        '    {"title": "Slide title", "bullets": ["point 1", "point 2", "point 3"]}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Exactly the requested slide count.\n"
        "- 3 to 5 concise bullets per slide.\n"
        "- Content must be specific, no generic filler."
    )

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    last_error: Exception | None = None
    for model in MODEL_CANDIDATES:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a presentation writing expert."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            content = response.choices[0].message.content or ""
            parsed = _extract_json(content)
            slides = _normalize_slides(topic, slide_count, parsed)
            logger.info("Slides generated via model: %s", model)
            return slides
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter model failed (%s): %s", model, exc)

    logger.error("All OpenRouter attempts failed: %s", last_error)
    return _fallback_slides(topic, slide_count)


async def generate_slide_content(
    topic: str,
    slide_count: int,
    template_type: int | None = None,
    presentation_type: int | None = None,
) -> list[SlideContent]:
    effective_template_type = template_type if template_type is not None else presentation_type
    if effective_template_type is None:
        effective_template_type = 1

    try:
        return await asyncio.to_thread(_generate_sync, topic, slide_count, int(effective_template_type))
    except Exception as exc:
        logger.exception("Unexpected error while generating slides: %s", exc)
        return _fallback_slides(topic, slide_count)
