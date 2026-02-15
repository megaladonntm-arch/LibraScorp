from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets_pdf"
DEFAULT_MODEL = "openai/gpt-oss-120b:free"
FALLBACK_MODELS = (
    "openai/gpt-4o-mini",
    "openai/gpt-4.1-mini",
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


def _model_candidates() -> list[str]:
    from_env = os.getenv("OPENROUTER_MODEL", "").strip()
    candidates: list[str] = []
    if from_env:
        for item in from_env.split(","):
            model = item.strip()
            if model:
                candidates.append(model)

    for model in (DEFAULT_MODEL, *FALLBACK_MODELS):
        if model not in candidates:
            candidates.append(model)
    return candidates


def _extract_json(payload: str) -> dict:
    raw = payload.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError("AI response does not contain JSON.")
        return json.loads(match.group(0))


def _fallback_slides(topic: str, slide_count: int) -> list[SlideContent]:
    slides: list[SlideContent] = []
    for idx in range(1, slide_count + 1):
        if idx == 1:
            slides.append(
                SlideContent(
                    title=f"{topic}: обзор",
                    bullets=[
                        "Краткое введение в тему.",
                        "Почему тема важна сейчас.",
                        "Что будет разобрано в презентации.",
                    ],
                )
            )
        elif idx == slide_count:
            slides.append(
                SlideContent(
                    title="Выводы",
                    bullets=[
                        "Ключевые идеи по теме.",
                        "Практические шаги применения.",
                        "Рекомендации для следующего этапа.",
                    ],
                )
            )
        else:
            slides.append(
                SlideContent(
                    title=f"{topic}: слайд {idx}",
                    bullets=[
                        "Основной тезис слайда.",
                        "Факты и аргументы по тезису.",
                        "Промежуточный вывод.",
                    ],
                )
            )
    return slides


def _normalize_slides(topic: str, slide_count: int, slides_raw: object) -> list[SlideContent]:
    if not isinstance(slides_raw, list):
        return _fallback_slides(topic=topic, slide_count=slide_count)

    slides: list[SlideContent] = []
    for item in slides_raw[:slide_count]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip() or "Без названия"
        bullets_raw = item.get("bullets", [])
        if not isinstance(bullets_raw, list):
            bullets_raw = []
        bullets = [str(x).strip() for x in bullets_raw if str(x).strip()]
        if not bullets:
            bullets = ["Основная мысль слайда."]
        slides.append(SlideContent(title=title, bullets=bullets[:5]))

    if len(slides) < slide_count:
        slides.extend(_fallback_slides(topic=topic, slide_count=slide_count - len(slides)))
    return slides[:slide_count]


def _generate_sync(topic: str, slide_count: int, template_type: int) -> list[SlideContent]:
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENROUTER_API_KEY is empty. Using fallback slide text.")
        return _fallback_slides(topic=topic, slide_count=slide_count)

    prompt = (
        "Сгенерируй текст презентации на русском языке.\n"
        f"Тема: {topic}\n"
        f"Количество слайдов: {slide_count}\n"
        f"Тип шаблона: {template_type}\n\n"
        "Верни строго JSON-объект без markdown и без лишнего текста.\n"
        "Формат:\n"
        "{\n"
        '  "slides": [\n'
        '    {"title": "Заголовок", "bullets": ["пункт 1", "пункт 2", "пункт 3"]}\n'
        "  ]\n"
        "}\n\n"
        "Требования:\n"
        "- Ровно столько элементов в slides, сколько задано в количестве слайдов.\n"
        "- Для каждого слайда 3-5 кратких пунктов.\n"
        "- Пункты должны быть содержательными, без общих фраз."
    )

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    last_error: Exception | None = None
    for model in _model_candidates():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ты эксперт по созданию презентаций."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                extra_body={"reasoning": {"enabled": False}},
            )
            content = response.choices[0].message.content or ""
            data = _extract_json(content)
            slides = _normalize_slides(topic=topic, slide_count=slide_count, slides_raw=data.get("slides"))
            logger.info("Slides generated via OpenRouter model: %s", model)
            return slides
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter generation failed for model '%s': %s", model, exc)

    logger.error("All OpenRouter attempts failed: %s", last_error)
    return _fallback_slides(topic=topic, slide_count=slide_count)


async def generate_slide_content(
    topic: str,
    slide_count: int,
    template_type: int,
) -> list[SlideContent]:
    try:
        return await asyncio.to_thread(_generate_sync, topic, slide_count, template_type)
    except Exception as exc:
        logger.exception("Unexpected error while generating slides: %s", exc)
        return _fallback_slides(topic=topic, slide_count=slide_count)
