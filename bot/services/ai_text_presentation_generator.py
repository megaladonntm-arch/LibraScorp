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
        intro_title = f"{topic}: Overview and Introduction"
        intro_bullets = [
            "Context and relevance: why this topic matters and its business importance.",
            "Key questions this presentation will answer with data-driven insights.",
            "Expected outcomes and practical value for stakeholders.",
        ]
        body_title = f"{topic}: Detailed Analysis"
        body_bullets = [
            "Core concept with practical applications and real-world examples.",
            "Key data, statistics, and evidence supporting the main idea.",
            "Implementation guidance and best practices for effective execution.",
        ]
        end_title = "Conclusion and Next Steps"
        end_bullets = [
            "Summary of findings and key recommendations from the presentation.",
            "Strategic priorities and action plan for implementation.",
            "Next steps, timeline, and success metrics to measure progress.",
        ]
    elif lang == "uz":
        intro_title = f"{topic}: Kirish va Ijobiy Ko'rikka Olish"
        intro_bullets = [
            "Kontekst va dolzarbligi: nega bu mavzu muhim va biznesga ta'sir qiladi.",
            "Strategik savollar: taqdimot javob beradigan asosiy masalalar.",
            "Kutilayotgan natijalar va stakeholderlar uchun amaliy foyda.",
        ]
        body_title = f"{topic}: Batafsil Tahlil"
        body_bullets = [
            "Asosiy tushuncha aqliy ta'rif va haqiqiy misollar bilan.",
            "Tegishli ma'lumotlar, statistika va isboti qo'llaniladigan faktlar.",
            "Amaliy ko'rsatmalar va eng yaxshi amaliyotlar bilan ijro rejasi.",
        ]
        end_title = "Xulosa va Keyingi Qadamlar"
        end_bullets = [
            "Asosiy topilmalar va eng muhim tavsiyalar qisqacha.",
            "Strategik ustuvor yo'nalishlar va ijro rejasi.",
            "Aniq keyingi qadamlar, vaqt jadavali va natija ko'rsatkichlari.",
        ]
    else:
        intro_title = f"{topic}: Полный обзор и введение"
        intro_bullets = [
            "Контекст и актуальность: почему эта тема важна для организации сейчас.",
            "Ключевые вопросы, на которые дадут ответ данные и анализ в презентации.",
            "Ожидаемые результаты и практическая ценность для аудитории.",
        ]
        body_title = f"{topic}: Детальный анализ"
        body_bullets = [
            "Основная концепция с примерами применения и реальными сценариями.",
            "Ключевые данные, статистика и факты, подтверждающие идеи.",
            "Практические рекомендации и методологии для успешного внедрения.",
        ]
        end_title = "Выводы и следующие шаги"
        end_bullets = [
            "Резюме главных выводов и ключевых рекомендаций из презентации.",
            "Стратегические приоритеты и план действий по внедрению.",
            "Конкретные шаги, сроки и показатели для отслеживания прогресса.",
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
            bullets.append(bullet[:500])
        if not bullets:
            if lang == "en":
                bullets = ["Main point of this slide."]
            elif lang == "uz":
                bullets = ["Ushbu slaydning asosiy g'oyasi."]
            else:
                bullets = ["Главная мысль слайда."]
        slides.append(SlideContent(title=title, bullets=bullets[:4]))

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
        "Create deep, practical, audience-ready slide content for a presentation. Return strict JSON only.\n"
        f"Topic: {topic}\n"
        f"Slide count: {slide_count}\n"
        f"Template type: {template_type}\n\n"
        f"Output language: {language_name} (code: {language_code})\n\n"
        "Format:\n"
        "{\n"
        '  "slides": [\n'
        '    {"title": "Clear title", "bullets": ["point 1", "point 2", "point 3", "point 4"]}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Exactly the requested slide count.\n"
        "- 3 to 4 HIGH-QUALITY bullets per slide (not too many, but substantive).\n"
        "- Each bullet: one complete, well-written sentence (120-200 chars). Clear and professional.\n"
        "- Slide 1: engaging title slide with main topic and relevance.\n"
        "- Last slide: clear conclusions and next steps.\n"
        "- Middle slides: key ideas with reasons, specific examples, and practical application.\n"
        "- Write clearly and grammatically - no redundancy, every word counts.\n"
        "- Explain not only facts, but also context, cause-effect, implications, and actionable recommendations.\n"
        "- Include relevant examples, metrics, or practical tips where applicable.\n"
        "- Make the slide visually balanced - not too crowded, easy to read.\n"
        "- Each slide must have unique, non-repetitive content.\n"
        "- Avoid one-liners, generic statements, and obvious textbook facts.\n"
        "- Prefer concrete, decision-useful information over abstract wording.\n"
        "- No markdown formatting, no code blocks, JSON only."
    )

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    last_error: Exception | None = None
    for model in settings.openrouter_models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior presentation copywriter and analyst. "
                            "Write content that is complete, concrete, and decision-useful. "
                            "Do not produce shallow summaries: include reasoning, implications, and practical actions."
                        ),
                    },
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
    source_material: str | None = None,
) -> list[SlideContent]:
    effective_template_type = template_type if template_type is not None else presentation_type
    if effective_template_type is None:
        effective_template_type = 1

    try:
        effective_lang = _normalize_language_code(lang)
        enriched_topic = topic
        if source_material:
            normalized_source = re.sub(r"\s+", " ", source_material).strip()[:12000]
            enriched_topic = (
                f"{topic}\n\n"
                "Source material (must be used as primary basis):\n"
                f"{normalized_source}\n\n"
                "Important: use this source as factual base for slide content."
            )
        return await _generate_async(enriched_topic, slide_count, int(effective_template_type), effective_lang)
    except Exception as exc:
        logger.exception("Unexpected error while generating slides: %s", exc)
        return _fallback_slides(topic, slide_count, _normalize_language_code(lang))
