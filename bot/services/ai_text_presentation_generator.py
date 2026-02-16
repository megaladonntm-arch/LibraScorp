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
            "Complete context and background: why this topic matters now and its relevance to business objectives.",
            "The specific problems and challenges this presentation will address and solutions we'll explore.",
            "Key strategic questions this presentation will answer with data-driven insights.",
            "Expected business outcomes and tangible value for the organization and stakeholders.",
            "Overview of the presentation structure and what will be covered in each section.",
        ]
        body_title = f"{topic}: Detailed Analysis"
        body_bullets = [
            "Core concept explained thoroughly with definitions, context, and real-world applications.",
            "Concrete examples, case studies, and detailed scenarios demonstrating the concept in practice.",
            "Relevant data, statistics, metrics, and benchmarks supporting the main idea.",
            "Practical implementation guidance, best practices, and proven methodologies.",
            "Potential challenges, risks, and mitigation strategies for successful execution.",
        ]
        end_title = "Comprehensive Conclusion and Next Steps"
        end_bullets = [
            "Complete summary of all major findings, recommendations, and conclusions from the presentation.",
            "Strategic priorities and action plan: detailed roadmap for implementation.",
            "Specific next steps, responsibilities, timelines, and key performance indicators to track success.",
            "Expected outcomes and long-term impact on business goals and organizational growth.",
            "Q&A and resources available for further information and team support.",
        ]
    elif lang == "uz":
        intro_title = f"{topic}: Kirish va Ijobiy Ko'rikka Olish"
        intro_bullets = [
            "To'liq kontekst va fon: nega bu mavzu muhim va uning daromadgim o'rni nima.",
            "Ushbu taqdimot javob beradigan muammolar, qiyinchiliklar va yechimlar.",
            "Strategik savollar: taqdimot qanday ma'lumotlar asosida javob beradi.",
            "Kutilayotgan biznes natijalar va tashkilot uchun amaliy foyda.",
            "Taqdimotning tuzilishi: har bir bo'lim nima o'z ichiga oladi.",
        ]
        body_title = f"{topic}: Batafsil Tahlil"
        body_bullets = [
            "Asosiy tushuncha to'liq izohlanadi: ta'rif, kontekst va haqiqiy qo'llaniladigan misollar.",
            "Konkret holat o'rganilari, ishchi oladigan mashhur misollar va batafsil stsenariylar.",
            "Tegishli ma'lumotlar, statistika, metrikalalar va soha bo'yicha taqqoslamalar.",
            "Amaliy tatbiq bo'yicha ko'rsatmalar, eng yaxshi amaliyotlar va isbotlangan metodlar.",
            "Mumkin bo'lgan muammolar, xطarlar va muvaffaqiyatli ijro uchun xavf kamaytirish strategiyasi.",
        ]
        end_title = "Keng Ko'lamli Xulosa va Keyingi Qadamlar"
        end_bullets = [
            "Barcha asosiy topilmalar, tavsiyalar va taqdimotdan chiqarilgan xulosalar qisqacha.",
            "Strategik ustuvor yo'nalishlar va amaliy reja: batafsil ijro yo'limasi.",
            "Aniq keyingi qadamlar, mas'uliyatlar, vaqt jadavali va muvaffaqiyat ko'rsatkich.",
            "Kutilayotgan natijalar va biznes maqsadlariga hamda tashkilot rivojlanishiga uzoq muddatli ta'sir.",
            "Savollar-javoblar va batafsil ma'lumot uchun mavjud resurslar.",
        ]
    else:
        intro_title = f"{topic}: Полный обзор и введение"
        intro_bullets = [
            "Полный контекст и история: почему эта тема критически важна для организации и актуальна сейчас.",
            "Конкретные проблемы и вызовы, которые рассматривает презентация, а также предлагаемые решения.",
            "Ключевые стратегические вопросы, на которые дадут ответ данные и анализ в презентации.",
            "Ожидаемые результаты для бизнеса и конкретная ценность для организации и её уровней управления.",
            "Обзор структуры презентации, что будет рассмотрено в каждом разделе и как они связаны.",
        ]
        body_title = f"{topic}: Детальный анализ"
        body_bullets = [
            "Основная концепция объяснена полностью с определениями, историческим контекстом и примерами применения.",
            "Конкретные примеры, кейс-стади, реальные сценарии, демонстрирующие как это работает на практике.",
            "Актуальные данные, статистика, метрики, бенчмарки и исследования, подтверждающие основные идеи.",
            "Практические рекомендации по внедрению, лучшие практики и проверенные методологии из разных компаний.",
            "Возможные трудности, риски, препятствия и конкретные стратегии их преодоления для успеха.",
        ]
        end_title = "Комплексное заключение и следующие шаги"
        end_bullets = [
            "Полное резюме всех главных выводов, рекомендаций и заключений из всей презентации.",
            "Стратегические приоритеты и план действий: детальная дорожная карта по внедрению.",
            "Конкретные следующие шаги, ответственные лица, сроки выполнения и ключевые показатели успеха.",
            "Ожидаемые результаты и долгосрочное влияние на достижение бизнес-целей и развитие организации.",
            "Дополнительные ресурсы, поддержка команды и варианты получения дополнительной информации.",
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
        slides.append(SlideContent(title=title, bullets=bullets[:7]))

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
        "Create comprehensive, detailed slide content for a professional business presentation. Return strict JSON only.\n"
        f"Topic: {topic}\n"
        f"Slide count: {slide_count}\n"
        f"Template type: {template_type}\n\n"
        f"Output language: {language_name} (code: {language_code})\n\n"
        "Format:\n"
        "{\n"
        '  "slides": [\n'
        '    {"title": "Slide title", "bullets": ["point 1", "point 2", "point 3", "point 4", "point 5"]}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Exactly the requested slide count.\n"
        "- 5 to 7 detailed and comprehensive bullets per slide (not concise, but DETAILED).\n"
        "- Each bullet must be thorough, substantive, and informative - write fully and completely.\n"
        "- Slide 1 is a compelling introduction with context and importance.\n"
        "- Final slide is comprehensive conclusion with summary and forward-looking recommendations.\n"
        "- Each bullet should be specific, detailed, and actionable with context and reasoning.\n"
        "- Include concrete facts, realistic examples, detailed metrics, statistics, case studies, or thorough recommendations.\n"
        "- Expand on each point - explain WHY, HOW, and provide detailed context.\n"
        "- Bullets should be substantial (2-3 sentences each), not one-liners.\n"
        "- Avoid repeating the same idea across slides - each point should add new value.\n"
        "- Be comprehensive and thorough on the topic - write in detail across all slides.\n"
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
