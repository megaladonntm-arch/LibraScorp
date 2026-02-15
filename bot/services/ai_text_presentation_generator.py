from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from bot.config import load_settings

logger = logging.getLogger(__name__)
settings = load_settings()

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets_pdf"
LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
    "uz": "Uzbek",
}


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


def _normalize_language_code(lang: str | None) -> str:
    return lang if lang in LANGUAGE_NAMES else "ru"


def _fallback_slides(topic: str, slide_count: int, lang: str) -> list[SlideContent]:
    if lang == "en":
        intro_title = f"{topic}: Overview"
        intro_bullets = [
            "Context and relevance of the topic.",
            "Key questions this presentation answers.",
            "Expected practical outcomes.",
        ]
        body_title = f"{topic}: Slide"
        body_bullets = [
            "Core idea in one sentence.",
            "Concrete example, fact, or scenario.",
            "Practical takeaway for the audience.",
        ]
        end_title = "Conclusion"
        end_bullets = [
            "Main conclusions and priorities.",
            "Recommended next steps.",
            "Short final summary.",
        ]
    elif lang == "uz":
        intro_title = f"{topic}: Kirish"
        intro_bullets = [
            "Mavzuning mazmuni va dolzarbligi.",
            "Taqdimot javob beradigan asosiy savollar.",
            "Amaliy natijalar.",
        ]
        body_title = f"{topic}: Slayd"
        body_bullets = [
            "Asosiy g'oya bir jumlada.",
            "Aniq misol yoki fakt.",
            "Tinglovchi uchun amaliy xulosa.",
        ]
        end_title = "Xulosa"
        end_bullets = [
            "Asosiy xulosalar va ustuvor yo'nalishlar.",
            "Keyingi amaliy qadamlar.",
            "Qisqa yakuniy fikr.",
        ]
    else:
        intro_title = f"{topic}: обзор"
        intro_bullets = [
            "Контекст темы и её актуальность.",
            "На какие вопросы ответит презентация.",
            "Практический результат для аудитории.",
        ]
        body_title = f"{topic}: слайд"
        body_bullets = [
            "Ключевая мысль одним тезисом.",
            "Конкретный пример или факт.",
            "Практический вывод для слушателя.",
        ]
        end_title = "Заключение"
        end_bullets = [
            "Главные выводы и приоритеты.",
            "Рекомендуемые следующие шаги.",
            "Короткий финальный итог.",
        ]

    slides: list[SlideContent] = []
    for i in range(1, slide_count + 1):
        if i == 1:
            slides.append(
                SlideContent(
                    title=intro_title,
                    bullets=intro_bullets,
                )
            )
        elif i == slide_count:
            slides.append(
                SlideContent(
                    title=end_title,
                    bullets=end_bullets,
                )
            )
        else:
            slides.append(
                SlideContent(
                    title=f"{body_title} {i}",
                    bullets=body_bullets,
                )
            )
    return slides


def _normalize_slides(topic: str, slide_count: int, raw: Any, lang: str) -> list[SlideContent]:
    if isinstance(raw, dict):
        raw = raw.get("slides")

    if not isinstance(raw, list):
        return _fallback_slides(topic, slide_count, lang)

    slides: list[SlideContent] = []
    for item in raw[:slide_count]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            if lang == "en":
                title = "Untitled"
            elif lang == "uz":
                title = "Nomsiz"
            else:
                title = "Без названия"
        bullets_raw = item.get("bullets", [])
        if not isinstance(bullets_raw, list):
            bullets_raw = []
        bullets: list[str] = []
        seen: set[str] = set()
        for value in bullets_raw:
            bullet = re.sub(r"\s+", " ", str(value).strip())
            bullet = re.sub(r"^[\-\*\d\.\)\s]+", "", bullet).strip()
            if not bullet:
                continue
            key = bullet.casefold()
            if key in seen:
                continue
            seen.add(key)
            bullets.append(bullet[:220])
        if not bullets:
            if lang == "en":
                bullets = ["Main point of this slide."]
            elif lang == "uz":
                bullets = ["Ushbu slaydning asosiy g'oyasi."]
            else:
                bullets = ["Главная мысль слайда."]
        slides.append(SlideContent(title=title, bullets=bullets[:5]))

    if len(slides) < slide_count:
        fallback = _fallback_slides(topic, slide_count, lang)
        slides.extend(fallback[len(slides):slide_count])

    return slides[:slide_count]


async def _generate_async(topic: str, slide_count: int, template_type: int, lang: str) -> list[SlideContent]:
    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        logger.error("OPENROUTER_API_KEY is empty in .env")
        return _fallback_slides(topic, slide_count, lang)

    language_code = _normalize_language_code(lang)
    language_name = LANGUAGE_NAMES[language_code]

    prompt = (
        "Create high-quality slide content for a business presentation. Return strict JSON only.\n"
        f"Topic: {topic}\n"
        f"Slide count: {slide_count}\n"
        f"Template type: {template_type}\n\n"
        f"Output language: {language_name} (code: {language_code})\n\n"
        "Format:\n"
        "{\n"
        '  "slides": [\n'
        '    {"title": "Slide title", "bullets": ["point 1", "point 2", "point 3"]}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Exactly the requested slide count.\n"
        "- 3 to 5 concise bullets per slide.\n"
        "- Slide 1 is an engaging introduction, final slide is conclusion/next steps.\n"
        "- Each bullet should be specific and actionable, avoid generic filler.\n"
        "- Prefer concrete facts, realistic examples, metrics, or practical recommendations.\n"
        "- Avoid repeating the same bullet wording across slides.\n"
        "- No markdown, no code fences, no commentary outside JSON."
    )

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    last_error: Exception | None = None
    for model in settings.openrouter_models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a senior presentation copywriter. You produce clear, specific, audience-ready slide text."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.45,
            )
            content = response.choices[0].message.content or ""
            parsed = _extract_json(content)
            slides = _normalize_slides(topic, slide_count, parsed, language_code)
            logger.info("Slides generated via model: %s", model)
            return slides
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter model failed (%s): %s", model, exc)

    logger.error("All OpenRouter attempts failed: %s", last_error)
    return _fallback_slides(topic, slide_count, language_code)


async def generate_slide_content(
    topic: str,
    slide_count: int,
    template_type: int | None = None,
    presentation_type: int | None = None,
    lang: str = "ru",
) -> list[SlideContent]:
    effective_template_type = template_type if template_type is not None else presentation_type
    if effective_template_type is None:
        effective_template_type = 1

    try:
        effective_lang = _normalize_language_code(lang)
        return await _generate_async(topic, slide_count, int(effective_template_type), effective_lang)
    except Exception as exc:
        logger.exception("Unexpected error while generating slides: %s", exc)
        return _fallback_slides(topic, slide_count, _normalize_language_code(lang))
