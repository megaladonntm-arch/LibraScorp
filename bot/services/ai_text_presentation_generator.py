from __future__ import annotations

import json
import logging
import random
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

SLIDE_MODE_RULES = {
    "intro": "Set context, relevance, scope, and what the audience will get.",
    "facts": "Prioritize concrete facts, numbers, metrics, and verifiable statements.",
    "deep": "Provide full explanation: causes, mechanisms, implications, and decisions.",
    "interesting": "Add non-obvious insights, surprising angles, and meaningful details.",
    "comparison": "Compare approaches/options with trade-offs and selection criteria.",
    "case": "Use a practical scenario or mini-case with concrete actions and outcomes.",
    "actions": "Focus on implementation steps, owners, timeline, and success metrics.",
    "risks": "Highlight risks, constraints, failure points, and mitigation actions.",
    "conclusion": "Summarize key takeaways, strategic priorities, and next steps.",
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


def _build_slide_modes(slide_count: int) -> list[str]:
    if slide_count <= 0:
        return []
    if slide_count == 1:
        return ["intro"]

    middle_modes = ["facts", "deep", "interesting", "comparison", "case", "actions", "risks"]
    rng = random.SystemRandom()

    plan = ["intro"]
    middle_needed = max(0, slide_count - 2)
    middle: list[str] = []
    while len(middle) < middle_needed:
        chunk = middle_modes[:]
        rng.shuffle(chunk)
        middle.extend(chunk)
    plan.extend(middle[:middle_needed])
    plan.append("conclusion")
    return plan


def _mode_lines_for_prompt(slide_modes: list[str]) -> str:
    lines: list[str] = []
    for idx, mode in enumerate(slide_modes, start=1):
        lines.append(f"- Slide {idx}: {SLIDE_MODE_RULES.get(mode, SLIDE_MODE_RULES['deep'])}")
    return "\n".join(lines)


def _fallback_mode_slide(topic: str, index: int, mode: str, lang: str) -> SlideContent:
    if lang == "en":
        definitions = {
            "intro": (
                f"{topic}: Why It Matters",
                [
                    "Business context, strategic relevance, and why this topic requires immediate attention now.",
                    "Key questions this presentation will answer to support better decisions and alignment.",
                    "Expected outcomes and practical value for stakeholders, teams, and execution planning.",
                ],
            ),
            "facts": (
                f"{topic}: Facts and Metrics ({index})",
                [
                    "Core facts and baseline indicators that define the current state of this topic in practice.",
                    "Quantitative signals and measurable patterns used to evaluate performance and progress.",
                    "Evidence-based observations showing where gains, losses, or bottlenecks appear most clearly.",
                ],
            ),
            "deep": (
                f"{topic}: Deep Analysis ({index})",
                [
                    "Root causes and structural drivers that shape outcomes, risks, and long-term impact.",
                    "How key mechanisms interact in real conditions and why common assumptions may fail.",
                    "Decision implications for leadership, process design, and resource prioritization.",
                ],
            ),
            "interesting": (
                f"{topic}: Insights and Interesting Angles ({index})",
                [
                    "A non-obvious insight that reframes the topic and reveals hidden leverage points.",
                    "A meaningful detail or pattern that usually gets ignored but affects real outcomes.",
                    "An interesting fact linked to practical interpretation rather than isolated trivia.",
                ],
            ),
            "comparison": (
                f"{topic}: Option Comparison ({index})",
                [
                    "Comparison of viable approaches with clear strengths, weaknesses, and use conditions.",
                    "Trade-offs across cost, speed, quality, and operational complexity for each option.",
                    "Selection criteria to choose the most suitable path for your current constraints.",
                ],
            ),
            "case": (
                f"{topic}: Practical Scenario ({index})",
                [
                    "A realistic scenario describing initial conditions, actions taken, and execution choices.",
                    "Observed results, key turning points, and what influenced the final outcome most.",
                    "Transferable lessons that can be applied with adjustments in your environment.",
                ],
            ),
            "actions": (
                f"{topic}: Implementation Plan ({index})",
                [
                    "Step-by-step implementation path with concrete actions and sequence dependencies.",
                    "Roles, ownership, and timeline checkpoints required to keep delivery on track.",
                    "Success metrics and feedback loops to verify impact and adjust quickly.",
                ],
            ),
            "risks": (
                f"{topic}: Risks and Mitigation ({index})",
                [
                    "Major risks and constraints that can derail results if not addressed early.",
                    "Early warning indicators that help detect failure patterns before escalation.",
                    "Mitigation actions with contingency options and accountability assignments.",
                ],
            ),
            "conclusion": (
                "Conclusion and Next Steps",
                [
                    "Summary of key findings and what they mean for strategy, execution, and ownership.",
                    "Priority actions to take first, with expected impact and short-term milestones.",
                    "A clear next-step roadmap with measurable outcomes and review checkpoints.",
                ],
            ),
        }
    elif lang == "uz":
        definitions = {
            "intro": (
                f"{topic}: Nima Uchun Muhim",
                [
                    "Mavzuning biznesdagi o'rni, dolzarbligi va nega aynan hozir e'tibor talab qilishi.",
                    "Taqdimot davomida javob beriladigan asosiy savollar va qarorlar uchun yo'nalish.",
                    "Stakeholderlar uchun kutilayotgan natijalar va amaliy qiymatning aniq ko'rinishi.",
                ],
            ),
            "facts": (
                f"{topic}: Faktlar va Ko'rsatkichlar ({index})",
                [
                    "Joriy holatni ifodalovchi asosiy faktlar va bazaviy indikatorlar tahlili.",
                    "Natijani baholashga xizmat qiladigan raqamlar, o'lchovlar va dinamik tendensiyalar.",
                    "Eng katta o'sish yoki muammo nuqtalarini ko'rsatadigan dalillarga asoslangan xulosalar.",
                ],
            ),
            "deep": (
                f"{topic}: Chuqur Tahlil ({index})",
                [
                    "Natijalarni belgilovchi ildiz sabablari va tizimli omillarni batafsil sharhlash.",
                    "Asosiy mexanizmlarning o'zaro ta'siri hamda noto'g'ri taxminlar xavfini ko'rsatish.",
                    "Rahbariyat va jamoalar uchun qaror qabul qilishdagi amaliy oqibatlar.",
                ],
            ),
            "interesting": (
                f"{topic}: Qiziqarli Insightlar ({index})",
                [
                    "Mavzuga boshqacha qarash beradigan noan'anaviy, lekin foydali insight taqdim etish.",
                    "Ko'pincha e'tibordan chetda qoladigan, ammo natijaga kuchli ta'sir qiladigan detal.",
                    "Oddiy trivia emas, balki amaliy talqin beruvchi qiziqarli fakt va xulosa.",
                ],
            ),
            "comparison": (
                f"{topic}: Variantlar Taqqoslovi ({index})",
                [
                    "Mumkin bo'lgan yondashuvlarni kuchli va zaif tomonlari bilan taqqoslash.",
                    "Har bir variant bo'yicha xarajat, tezlik, sifat va murakkablikdagi trade-offlar.",
                    "Hozirgi cheklovlar ostida eng mos variantni tanlash mezonlarini berish.",
                ],
            ),
            "case": (
                f"{topic}: Amaliy Keys ({index})",
                [
                    "Boshlang'ich holat, qilingan harakatlar va qabul qilingan qarorlar ketma-ketligi.",
                    "Olingan natijalar, burilish nuqtalari va eng katta ta'sir qilgan omillar.",
                    "Sizning sharoitingizga moslab qo'llash mumkin bo'lgan amaliy darslar.",
                ],
            ),
            "actions": (
                f"{topic}: Amalga Oshirish Rejasi ({index})",
                [
                    "Bosqichma-bosqich ijro rejasi va har bir bosqich o'rtasidagi bog'liqliklar.",
                    "Mas'ullar, rollar va muddatlar bo'yicha nazorat nuqtalarini belgilash.",
                    "Natijani o'lchash KPIlari va tezkor tuzatish uchun feedback mexanizmi.",
                ],
            ),
            "risks": (
                f"{topic}: Xatarlar va Himoya ({index})",
                [
                    "Natijani pasaytirishi mumkin bo'lgan asosiy xatarlar va operatsion cheklovlar.",
                    "Muammoni erta aniqlash uchun signal va indikatorlarni aniq ko'rsatish.",
                    "Mitigatsiya choralari, zaxira variantlar va javobgarlik taqsimoti.",
                ],
            ),
            "conclusion": (
                "Xulosa va Keyingi Qadamlar",
                [
                    "Asosiy xulosalar va ularning strategiya hamda ijroga ta'sirini umumlashtirish.",
                    "Eng ustuvor amallar, kutilayotgan ta'sir va qisqa muddatli milestonelar.",
                    "Aniq keyingi qadamlar yo'l xaritasi, KPI va qayta ko'rib chiqish nuqtalari.",
                ],
            ),
        }
    else:
        definitions = {
            "intro": (
                f"{topic}: Контекст и значимость",
                [
                    "Контекст темы, её актуальность и причины, почему ей нужно уделить внимание именно сейчас.",
                    "Ключевые вопросы презентации, которые помогут принимать более точные управленческие решения.",
                    "Ожидаемая практическая ценность и результат для команды, бизнеса и заинтересованных сторон.",
                ],
            ),
            "facts": (
                f"{topic}: Факты и метрики ({index})",
                [
                    "Ключевые факты и базовые показатели, которые описывают текущее состояние по теме.",
                    "Измеримые метрики и наблюдаемые тенденции, важные для оценки динамики и эффективности.",
                    "Данные и подтверждения, показывающие, где сосредоточены основные точки роста и риска.",
                ],
            ),
            "deep": (
                f"{topic}: Глубокий разбор ({index})",
                [
                    "Разбор первопричин и системных факторов, которые формируют результат в долгую.",
                    "Пояснение механизмов влияния и связей, из-за которых простые решения часто не срабатывают.",
                    "Практические выводы для стратегии, распределения ресурсов и приоритизации действий.",
                ],
            ),
            "interesting": (
                f"{topic}: Инсайты и интересные детали ({index})",
                [
                    "Неочевидный инсайт, который меняет взгляд на тему и открывает новую точку воздействия.",
                    "Интересная, но прикладная деталь, которую обычно упускают, хотя она влияет на итог.",
                    "Факт с объяснением его значения для практики, а не просто отдельная любопытная цифра.",
                ],
            ),
            "comparison": (
                f"{topic}: Сравнение подходов ({index})",
                [
                    "Сравнение рабочих вариантов с выделением сильных и слабых сторон каждого подхода.",
                    "Компромиссы по стоимости, скорости, качеству и сложности внедрения в реальных условиях.",
                    "Критерии выбора подхода с учетом текущих ограничений, целей и зрелости команды.",
                ],
            ),
            "case": (
                f"{topic}: Практический кейс ({index})",
                [
                    "Краткий сценарий из практики: исходные условия, действия команды и логика решений.",
                    "Полученные результаты, поворотные моменты и факторы, повлиявшие на итог сильнее всего.",
                    "Выводы, которые можно адаптировать и применить в вашем контексте без потери смысла.",
                ],
            ),
            "actions": (
                f"{topic}: План внедрения ({index})",
                [
                    "Пошаговый план реализации с понятной последовательностью действий и зависимостей.",
                    "Роли, зоны ответственности и контрольные точки по срокам для управляемого исполнения.",
                    "Метрики успеха и цикл обратной связи для корректировки курса по ходу внедрения.",
                ],
            ),
            "risks": (
                f"{topic}: Риски и меры ({index})",
                [
                    "Ключевые риски и ограничения, которые могут сорвать срок, качество или ожидаемый эффект.",
                    "Сигналы раннего предупреждения, позволяющие заранее увидеть проблемные сценарии.",
                    "План снижения рисков: превентивные меры, резервные варианты и ответственные роли.",
                ],
            ),
            "conclusion": (
                "Выводы и следующие шаги",
                [
                    "Итоговые выводы и их значение для стратегии, операционного управления и приоритетов.",
                    "Приоритетные действия на ближайший этап с ожидаемым эффектом и контрольными точками.",
                    "Четкий roadmap следующих шагов с измеримыми результатами и периодом ревизии.",
                ],
            ),
        }

    title, bullets = definitions.get(mode, definitions["deep"])
    return SlideContent(title=title, bullets=bullets)


def _fallback_slides(topic: str, slide_count: int, lang: str, slide_modes: list[str] | None = None) -> list[SlideContent]:
    effective_modes = slide_modes if slide_modes and len(slide_modes) >= slide_count else _build_slide_modes(slide_count)
    slides: list[SlideContent] = []
    for i in range(1, slide_count + 1):
        mode = effective_modes[i - 1] if i - 1 < len(effective_modes) else "deep"
        slides.append(_fallback_mode_slide(topic=topic, index=i, mode=mode, lang=lang))
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
    slide_modes = _build_slide_modes(slide_count)
    mode_plan = _mode_lines_for_prompt(slide_modes)

    prompt = (
        "Create deep, practical, audience-ready slide content for a presentation. Return strict JSON only.\n"
        f"Topic: {topic}\n"
        f"Slide count: {slide_count}\n"
        f"Template type: {template_type}\n\n"
        f"Output language: {language_name} (code: {language_code})\n\n"
        "Per-slide style plan (follow strictly so slides differ by style):\n"
        f"{mode_plan}\n\n"
        "Format:\n"
        "{\n"
        '  "slides": [\n'
        '    {"title": "Clear title", "bullets": ["point 1", "point 2", "point 3", "point 4"]}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Exactly the requested slide count.\n"
        "- Follow the per-slide style plan exactly by slide index.\n"
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
        "- Mix styles naturally across slides: facts, full analysis, interesting insights, and practical actions.\n"
        "- No markdown formatting, no code blocks, JSON only."
    )

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    timeout_sec = max(10, int(settings.openrouter_request_timeout_sec))
    max_attempts = max(1, int(settings.openrouter_max_model_attempts))
    models = settings.openrouter_models[:max_attempts]

    last_error: Exception | None = None
    for model in models:
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
                timeout=timeout_sec,
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
    return _fallback_slides(topic, slide_count, language_code, slide_modes=slide_modes)


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
