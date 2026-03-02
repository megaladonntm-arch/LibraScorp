from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
from html import escape
from pathlib import Path

from PIL import Image
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from bot.config import load_settings
from bot.db import (
    add_presentation_history,
    add_template_submission_log,
    add_user_tokens,
    get_premium_users,
    get_all_users,
    get_all_user_profiles,
    get_broadcast_user_ids,
    get_global_template_combos,
    get_recent_user_events,
    get_recent_template_submissions,
    get_user_ban,
    is_premium_user,
    get_user_data,
    get_user_profile,
    get_user_presentation_history,
    get_user_template_combos,
    remove_premium_user,
    remove_user_ban,
    remove_user_tokens,
    set_user_ban,
    set_premium_user,
    set_user_language,
    upsert_global_template_combo,
    upsert_user_template_combo,
)
from bot.i18n import color_hex_by_text, detect_language, is_action_text, t
from bot.keyboards.main_menu import (
    build_admin_panel_menu,
    build_color_menu,
    build_font_menu,
    build_language_menu,
    build_main_menu,
    build_premium_menu,
)
from bot.services.ai_text_presentation_generator import (
    BLUE_PLAYFUL_TEMPLATE_ID,
    get_template_name,
    generate_slide_content,
    list_presentation_types,
    resolve_pdf_template_asset,
)
from bot.services.presentation_builder import build_presentation_file
from bot.services.premium_voice_chat import ask_openrouter_from_text, transcribe_voice_file
from bot.services.topic_image_fetcher import fetch_topic_images, translate_topic_to_russian
from bot.services.wikipedia_source import fetch_russian_wikipedia_source
from bot.services.source_extractor import (
    MAX_DOWNLOAD_BYTES,
    SUPPORTED_TEXT_EXTENSIONS,
    extract_text_from_file,
    extract_text_from_url,
    is_http_url,
    normalize_source_text,
)

logger = logging.getLogger(__name__)
router = Router()
settings = load_settings()

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets_pdf"
MAX_TELEGRAM_MESSAGE_LEN = 3900
COMBO_PAGE_SIZE = 6
MAX_DEFAULT_COMBOS = 72
MAX_CUSTOM_SLIDE_IMAGE_BYTES = 10 * 1024 * 1024
MIN_CUSTOM_SLIDE_IMAGE_WIDTH = 400
MIN_CUSTOM_SLIDE_IMAGE_HEIGHT = 250

TEMPLATE_NAMES = {
    1: "Template 1",
    2: "Template 2",
    3: "Template 3",
    4: "Template 4",
    5: "Template 5",
    6: "Template 6",
    7: "Template 7",
    8: "Template 8",
    9: "Template 9",
    10: "Template 10",
    BLUE_PLAYFUL_TEMPLATE_ID: "Blue Playful (PDF full)",
}


def _combo_tab_order() -> tuple[str, str, str]:
    return ("default", "global", "my")


def _combo_tab_title(lang: str, tab: str) -> str:
    mapping = {
        "default": t(lang, "combo_tab_default"),
        "global": t(lang, "combo_tab_global"),
        "my": t(lang, "combo_tab_my"),
    }
    return mapping.get(tab, t(lang, "combo_tab_default"))


def _combo_label(name: str, seq: list[int]) -> str:
    sequence = ",".join(str(x) for x in seq[:6])
    if len(seq) > 6:
        sequence = f"{sequence},..."
    short_name = name if len(name) <= 24 else f"{name[:21]}..."
    return f"{short_name} | {sequence}"


def _build_combo_keyboard(
    lang: str,
    combo_groups: dict[str, list[str]],
    combo_options: dict[str, list[int]],
    combo_names: dict[str, str],
    active_tab: str,
    active_page: int,
) -> InlineKeyboardMarkup:
    tabs = [tab for tab in _combo_tab_order() if combo_groups.get(tab)]
    if not tabs:
        return InlineKeyboardMarkup(inline_keyboard=[])

    if active_tab not in tabs:
        active_tab = tabs[0]
    keys = combo_groups.get(active_tab, [])
    total_pages = max(1, (len(keys) + COMBO_PAGE_SIZE - 1) // COMBO_PAGE_SIZE)
    page = max(0, min(active_page, total_pages - 1))
    start = page * COMBO_PAGE_SIZE
    page_keys = keys[start : start + COMBO_PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    tab_row = [
        InlineKeyboardButton(
            text=f"• {_combo_tab_title(lang, tab)}" if tab == active_tab else _combo_tab_title(lang, tab),
            callback_data=f"cmb:tab:{tab}",
        )
        for tab in tabs
    ]
    rows.append(tab_row)

    for key in page_keys:
        name = combo_names.get(key, "Combo")
        seq = combo_options.get(key, [])
        rows.append(
            [
                InlineKeyboardButton(
                    text=_combo_label(name, seq),
                    callback_data=f"cmb:sel:{key}",
                )
            ]
        )

    if total_pages > 1:
        rows.append(
            [
                InlineKeyboardButton(text="◀", callback_data=f"cmb:page:{max(0, page - 1)}"),
                InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="cmb:noop"),
                InlineKeyboardButton(text="▶", callback_data=f"cmb:page:{min(total_pages - 1, page + 1)}"),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_combo_caption(
    lang: str,
    combo_groups: dict[str, list[str]],
    combo_options: dict[str, list[int]],
    active_tab: str,
    active_page: int,
    available: list[int],
) -> str:
    tabs = [tab for tab in _combo_tab_order() if combo_groups.get(tab)]
    if not tabs:
        return t(lang, "choose_combo_hint", available=", ".join(str(x) for x in available))
    if active_tab not in tabs:
        active_tab = tabs[0]

    tab_count = len(combo_groups.get(active_tab, []))
    counts = " | ".join(
        f"{_combo_tab_title(lang, tab)}: {len(combo_groups.get(tab, []))}" for tab in tabs
    )
    return (
        f"🎨 <b>{t(lang, 'choose_combo_title')}</b>\n"
        f"{counts}\n\n"
        f"{t(lang, 'choose_combo_hint', available=', '.join(str(x) for x in available))}\n"
        f"<b>{_combo_tab_title(lang, active_tab)}:</b> {tab_count}"
    )


def _normalize_template_sequence(raw: str, available: set[int]) -> list[int] | None:
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    if not parts:
        return None
    result: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        value = int(part)
        if value not in available:
            return None
        result.append(value)
    return result


def _expand_combo(sequence: list[int], slide_count: int) -> list[int]:
    if not sequence:
        return []
    expanded: list[int] = []
    while len(expanded) < slide_count:
        expanded.extend(sequence)
    return expanded[:slide_count]


def _default_combos(available: list[int], lang: str) -> list[tuple[str, list[int]]]:
    if not available:
        return []
    labels = {
        "ru": {
            "blue_pdf": "Blue Playful PDF (полный)",
            "all": "Все шаблоны по кругу",
            "forward": "Классика по возрастанию",
            "reverse": "Контраст по убыванию",
            "odd_even": "Нечетные + четные",
            "first": "Первые {n}",
            "last": "Последние {n}",
            "step": "Шаг {step}, смещение {offset}",
            "center_out": "Из центра к краям",
            "edges_in": "От краев к центру",
            "wave": "Волна (чередование краев)",
            "thirds": "Блоки: 1/3 + 2/3 + 3/3",
            "reverse_thirds": "Блоки: 3/3 + 2/3 + 1/3",
            "rotation": "Ротация +{shift}",
        },
        "en": {
            "blue_pdf": "Blue Playful PDF (full)",
            "all": "All templates loop",
            "forward": "Classic ascending",
            "reverse": "Contrast descending",
            "odd_even": "Odd + even",
            "first": "First {n}",
            "last": "Last {n}",
            "step": "Step {step}, offset {offset}",
            "center_out": "Center to edges",
            "edges_in": "Edges to center",
            "wave": "Wave (edge alternation)",
            "thirds": "Blocks: 1/3 + 2/3 + 3/3",
            "reverse_thirds": "Blocks: 3/3 + 2/3 + 1/3",
            "rotation": "Rotation +{shift}",
        },
        "uz": {
            "blue_pdf": "Blue Playful PDF (to'liq)",
            "all": "Barcha shablonlar aylana",
            "forward": "Klassik o'sish",
            "reverse": "Kamayish kontrasti",
            "odd_even": "Toq + juft",
            "first": "Birinchi {n}",
            "last": "Oxirgi {n}",
            "step": "Qadam {step}, siljish {offset}",
            "center_out": "Markazdan chetlarga",
            "edges_in": "Chetlardan markazga",
            "wave": "To'lqin (chetdan navbatma-navbat)",
            "thirds": "Bloklar: 1/3 + 2/3 + 3/3",
            "reverse_thirds": "Bloklar: 3/3 + 2/3 + 1/3",
            "rotation": "Aylantirish +{shift}",
        },
    }
    local = labels.get(lang, labels["ru"])

    combos: list[tuple[str, list[int]]] = []
    seen: set[tuple[int, ...]] = set()
    available_set = set(available)

    def add_combo(name: str, sequence: list[int]) -> None:
        cleaned: list[int] = []
        for item in sequence:
            if item in available_set:
                cleaned.append(item)
        if not cleaned:
            return
        key = tuple(cleaned)
        if key in seen:
            return
        seen.add(key)
        combos.append((name, cleaned))

    if BLUE_PLAYFUL_TEMPLATE_ID in available_set:
        add_combo(local["blue_pdf"], [BLUE_PLAYFUL_TEMPLATE_ID])
    for template_id in available:
        if template_id == BLUE_PLAYFUL_TEMPLATE_ID:
            continue
        if resolve_pdf_template_asset(template_id) is None:
            continue
        add_combo(f"PDF: {get_template_name(template_id)}", [template_id])

    add_combo(local["all"], available[:])
    add_combo(local["forward"], available[:])
    add_combo(local["reverse"], list(reversed(available)))
    odd_even = [item for item in available if item % 2 == 1] + [item for item in available if item % 2 == 0]
    add_combo(local["odd_even"], odd_even)

    for n in (2, 3, 4, 5, 6):
        add_combo(local["first"].format(n=n), available[:n])
        add_combo(local["last"].format(n=n), available[-n:])

    for step in (2, 3, 4):
        for offset in range(step):
            add_combo(local["step"].format(step=step, offset=offset), available[offset::step])

    center = len(available) // 2
    center_out: list[int] = []
    left = center - 1
    right = center
    while left >= 0 or right < len(available):
        if right < len(available):
            center_out.append(available[right])
            right += 1
        if left >= 0:
            center_out.append(available[left])
            left -= 1
    add_combo(local["center_out"], center_out)

    edges_in: list[int] = []
    l = 0
    r = len(available) - 1
    while l <= r:
        edges_in.append(available[l])
        if l != r:
            edges_in.append(available[r])
        l += 1
        r -= 1
    add_combo(local["edges_in"], edges_in)

    wave: list[int] = []
    for idx in range(len(available)):
        if idx % 2 == 0:
            wave.append(available[idx // 2])
        else:
            wave.append(available[-(idx // 2) - 1])
    add_combo(local["wave"], wave)

    third = max(1, len(available) // 3)
    block_a = available[:third]
    block_b = available[third : third * 2]
    block_c = available[third * 2 :]
    add_combo(local["thirds"], block_a + block_b + block_c)
    add_combo(local["reverse_thirds"], block_c + block_b + block_a)

    for shift in range(1, max(1, len(available))):
        add_combo(local["rotation"].format(shift=shift), available[shift:] + available[:shift])
        if len(combos) >= MAX_DEFAULT_COMBOS:
            break

    return combos[:MAX_DEFAULT_COMBOS]


async def send_template_preview(message: Message, template_num: int, lang: str, color: str = None) -> None:
    pdf_path = resolve_pdf_template_asset(template_num)
    if pdf_path is not None:
        template_name = TEMPLATE_NAMES.get(template_num, get_template_name(template_num))
        if pdf_path.exists():
            await message.answer_document(
                document=FSInputFile(str(pdf_path)),
                caption=f"<b>{template_name}</b>",
                parse_mode="HTML",
            )
        else:
            await message.answer(t(lang, "template_preview_missing", template=template_num))
        return

    if color and template_num <= 10:
        color_map = {"blue": "", "purple": "_purple", "red": "_red", "orange": "_orange", "green": "_green"}
        color_suffix = color_map.get(color.lower(), "")
        template_path = ASSETS_DIR / f"{template_num}{color_suffix}.png"
    else:
        template_path = ASSETS_DIR / f"{template_num}.png"
    
    if template_path.exists():
        photo = FSInputFile(str(template_path))
        template_name = TEMPLATE_NAMES.get(template_num, get_template_name(template_num))
        color_label = f" ({color.capitalize()})" if color else ""
        await message.answer_photo(
            photo=photo,
            caption=f"<b>{template_name}{color_label}</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer(t(lang, "template_preview_missing", template=template_num))


class PresentationForm(StatesGroup):
    slide_count = State()
    template_type = State()
    font_name = State()
    font_color = State()
    topic = State()
    source_material = State()
    creator_names = State()
    slide_images = State()


class AdminForm(StatesGroup):
    target_user_id = State()
    token_amount = State()
    remove_target_user_id = State()
    remove_token_amount = State()
    check_user_id = State()
    ban_target_user_id = State()
    ban_reason = State()
    unban_target_user_id = State()
    broadcast_text = State()
    profile_user_id = State()


class CustomTemplateForm(StatesGroup):
    name = State()
    photos = State()


def _is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == settings.admin_id)


def _next_template_number() -> int:
    current = list_presentation_types()
    return (max(current) + 1) if current else 1


async def _send_chunked_html(message: Message, lines: list[str]) -> None:
    buffer = ""
    for line in lines:
        candidate = f"{buffer}\n{line}" if buffer else line
        if len(candidate) > MAX_TELEGRAM_MESSAGE_LEN:
            if buffer:
                await message.answer(buffer, parse_mode="HTML")
                buffer = line
            else:
                await message.answer(line[:MAX_TELEGRAM_MESSAGE_LEN], parse_mode="HTML")
                buffer = ""
        else:
            buffer = candidate
    if buffer:
        await message.answer(buffer, parse_mode="HTML")


async def _send_chunked_plain(message: Message, text: str) -> None:
    payload = text.strip()
    if not payload:
        return
    start = 0
    step = MAX_TELEGRAM_MESSAGE_LEN
    while start < len(payload):
        await message.answer(payload[start : start + step])
        start += step


def _skip_words() -> set[str]:
    return {"skip", "пропустить", "нет", "yoq", "yo'q", "o'tkazib yuborish"}


def _done_words() -> set[str]:
    return {"done", "готово", "tayyor", "finish", "end"}


async def _cleanup_slide_image_temp_dir(state: FSMContext) -> None:
    data = await state.get_data()
    temp_dir_value = data.get("slide_images_temp_dir")
    if isinstance(temp_dir_value, str) and temp_dir_value.strip():
        shutil.rmtree(temp_dir_value, ignore_errors=True)


def _extract_supported_image_document_exts() -> tuple[str, ...]:
    return (".jpg", ".jpeg", ".png", ".webp")


async def _finalize_presentation_generation(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    if message.from_user is None:
        await _cleanup_slide_image_temp_dir(state)
        await state.clear()
        return

    data = await state.get_data()
    required_keys = ("topic", "slide_count", "font_name", "font_color", "font_color_label")
    if any(key not in data for key in required_keys):
        logger.warning("Presentation flow data is incomplete for user %s: keys=%s", message.from_user.id, list(data.keys()))
        await _cleanup_slide_image_temp_dir(state)
        await state.clear()
        await message.answer(
            t(lang, "flow_expired_restart"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return

    topic = str(data["topic"])
    slide_count = int(data["slide_count"])
    template_types = [int(x) for x in data.get("template_types", [])]
    font_name = str(data["font_name"])
    font_color = str(data["font_color"])
    font_color_label = str(data["font_color_label"])
    source_text = data.get("source_material")
    source_material = str(source_text) if isinstance(source_text, str) else None
    creator_raw = data.get("creator_names")
    creator_names = str(creator_raw) if isinstance(creator_raw, str) and creator_raw.strip() else None

    image_paths: list[str] = []
    for item in data.get("slide_image_paths", []):
        if isinstance(item, str) and Path(item).exists():
            image_paths.append(item)

    topic_for_russian_sources = topic
    if lang == "uz":
        topic_for_russian_sources = await translate_topic_to_russian(
            topic=topic,
            source_lang=lang,
            openrouter_api_key=settings.openrouter_api_key,
            openrouter_models=settings.openrouter_models,
            request_timeout_sec=settings.openrouter_request_timeout_sec,
            max_model_attempts=settings.openrouter_max_model_attempts,
        )

    min_images_required = max(2, slide_count * 2)
    if settings.auto_topic_images_enabled and len(image_paths) < min_images_required:
        missing_images = min(
            min_images_required - len(image_paths),
            settings.auto_topic_images_max_count,
        )
        topic_for_image_search = topic_for_russian_sources if topic_for_russian_sources.strip() else topic
        temp_dir_raw = data.get("slide_images_temp_dir")
        if isinstance(temp_dir_raw, str) and temp_dir_raw.strip():
            temp_dir = Path(temp_dir_raw)
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix="tg_slide_images_"))
            await state.update_data(slide_images_temp_dir=str(temp_dir))
        try:
            auto_images = await fetch_topic_images(
                topic=topic_for_image_search,
                limit=missing_images,
                destination_dir=temp_dir,
                min_width=MIN_CUSTOM_SLIDE_IMAGE_WIDTH,
                min_height=MIN_CUSTOM_SLIDE_IMAGE_HEIGHT,
                api_key=settings.pexels_api_key,
                timeout_sec=settings.pexels_request_timeout_sec,
            )
            if auto_images:
                image_paths.extend(str(path) for path in auto_images)
                await state.update_data(slide_image_paths=image_paths)
        except Exception:
            logger.exception("Failed to auto-fetch topic images for user %s", message.from_user.id)

    if image_paths and len(image_paths) < min_images_required:
        repeated: list[str] = []
        idx = 0
        while len(repeated) < min_images_required:
            repeated.append(image_paths[idx % len(image_paths)])
            idx += 1
        image_paths = repeated

    await message.answer(t(lang, "generating"))

    file_path: Path | None = None
    extra_slide = 1 if creator_names else 0
    try:
        wikipedia_source = await fetch_russian_wikipedia_source(topic_for_russian_sources)
        effective_source_material = source_material
        if wikipedia_source is not None:
            effective_source_material = (
                f"Russian Wikipedia article: {wikipedia_source.resolved_title}\n"
                f"URL: {wikipedia_source.page_url}\n"
                f"Content:\n{wikipedia_source.text}"
            )
        elif source_material:
            logger.warning(
                "Wikipedia source unavailable for topic '%s'; falling back to user-provided source.",
                topic_for_russian_sources,
            )

        slides = await generate_slide_content(
            topic=topic,
            slide_count=slide_count,
            template_type=template_types[0] if template_types else 1,
            lang=lang,
            source_material=effective_source_material,
        )
        file_path = await build_presentation_file(
            topic=topic,
            template_types=template_types,
            slides=slides,
            font_name=font_name,
            font_color=font_color,
            creator_names=creator_names,
            creator_title=t(lang, "creator_slide_title"),
            user_image_paths=image_paths,
        )
        await add_presentation_history(
            user_id=message.from_user.id,
            topic=topic,
            slide_count=slide_count + extra_slide,
            template_types=template_types,
            font_name=font_name,
            font_color=font_color,
            language=lang,
        )
        await message.answer_document(
            document=FSInputFile(file_path),
            caption=t(
                lang,
                "ready",
                slides=slide_count + extra_slide,
                font=font_name,
                color=font_color_label,
            ),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
    except Exception as e:
        logger.error("Failed to build presentation: %s", e)
        await message.answer(
            t(lang, "build_error", error=escape(str(e))),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
    finally:
        if file_path is not None:
            shutil.rmtree(file_path.parent, ignore_errors=True)
        await _cleanup_slide_image_temp_dir(state)
        await state.clear()


def _extract_command_user_id(message: Message) -> int | None:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    candidate = parts[1].strip()
    if not candidate.isdigit():
        return None
    return int(candidate)


def _extract_command_user_id_and_tail(message: Message) -> tuple[int | None, str]:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        return None, ""
    tail = parts[2].strip() if len(parts) >= 3 else ""
    return int(parts[1].strip()), tail


def _bool_label(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


async def _lang_and_tokens(message: Message) -> tuple[str, int]:
    if message.from_user is None:
        return "ru", settings.default_tokens
    tokens, lang = await get_user_data(message.from_user.id, settings.default_tokens)
    return lang, tokens


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    lang, tokens = await _lang_and_tokens(message)
    await message.answer(
        f"{t(lang, 'welcome')}\n\n{t(lang, 'tokens_info', tokens=tokens)}",
        reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
    )


@router.message(Command("help"))
@router.message(F.text.func(lambda value: is_action_text(value, "help")))
async def cmd_help(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    await message.answer(t(lang, "help"))


@router.message(Command("templates"))
async def cmd_templates(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    available = list_presentation_types()
    
    if not available:
        await message.answer(t(lang, "no_templates"))
        return
    
    await message.answer("📋 <b>Available Templates:</b>\n\n" + 
                        "\n".join(f"#{num}. {TEMPLATE_NAMES.get(num, get_template_name(num))}" 
                                 for num in sorted(available)),
                        parse_mode="HTML")
    
    ordered = sorted(available)
    if len(ordered) <= 10:
        preview_numbers = ordered
    else:
        middle_start = max(0, (len(ordered) // 2) - 2)
        middle_chunk = ordered[middle_start : middle_start + 4]
        preview_numbers = ordered[:3] + middle_chunk + ordered[-3:]
        preview_numbers = list(dict.fromkeys(preview_numbers))
    for template_num in preview_numbers:
        await send_template_preview(message, template_num, lang)
        await message.answer("➖")


@router.message(F.text.func(lambda value: is_action_text(value, "about")))
async def about_bot(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    await message.answer(t(lang, "about"))


@router.message(Command("my_presentations"))
@router.message(F.text.func(lambda value: is_action_text(value, "my_presentations")))
async def my_presentations(message: Message) -> None:
    if message.from_user is None:
        return

    lang, _ = await _lang_and_tokens(message)
    history = await get_user_presentation_history(message.from_user.id, limit=10)
    if not history:
        await message.answer(t(lang, "my_presentations_empty"))
        return

    localized = {
        "ru": ("Тема", "Слайды", "Шаблоны", "Шрифт", "Цвет"),
        "en": ("Topic", "Slides", "Templates", "Font", "Color"),
        "uz": ("Mavzu", "Slaydlar", "Shablonlar", "Shrift", "Rang"),
    }
    topic_label, slides_label, templates_label, font_label, color_label = localized.get(lang, localized["ru"])

    lines = [f"📚 <b>{t(lang, 'my_presentations_title')}</b>"]
    for item in history:
        created = item.created_at.strftime("%Y-%m-%d %H:%M UTC")
        templates = item.template_types or "-"
        lines.append(
            "\n"
            f"<b>#{item.id}</b> | {created}\n"
            f"{topic_label}: {escape(item.topic)}\n"
            f"{slides_label}: {item.slide_count} | {templates_label}: {escape(templates)}\n"
            f"{font_label}: {escape(item.font_name)} | {color_label}: {escape(item.font_color)}"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("my_combos"))
async def my_combos(message: Message) -> None:
    if message.from_user is None:
        return
    lang, _ = await _lang_and_tokens(message)
    combos = await get_user_template_combos(message.from_user.id)
    if not combos:
        await message.answer(t(lang, "my_combos_empty"))
        return

    lines = [f"🎛 <b>{t(lang, 'my_combos_title')}</b>"]
    for combo in combos:
        lines.append(f"{escape(combo.name)}: {escape(combo.templates_csv)}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("new_template"))
@router.message(F.text.func(lambda value: is_action_text(value, "create_template_from_scratch")))
async def start_custom_template_creation(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    lang, _ = await _lang_and_tokens(message)
    await state.clear()
    await state.set_state(CustomTemplateForm.name)
    await message.answer(t(lang, "ask_custom_template_name"), reply_markup=ReplyKeyboardRemove())


@router.message(CustomTemplateForm.name)
async def custom_template_name_step(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    lang, _ = await _lang_and_tokens(message)
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(t(lang, "combo_name_short"))
        return
    await state.update_data(custom_template_name=name[:80], custom_template_numbers=[])
    await state.set_state(CustomTemplateForm.photos)
    await message.answer(t(lang, "ask_custom_template_photos"))


@router.message(CustomTemplateForm.photos)
async def custom_template_photos_step(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await state.clear()
        return
    lang, _ = await _lang_and_tokens(message)
    done_words = {"готово", "done", "tayyor"}
    text_value = (message.text or "").strip().casefold()

    data = await state.get_data()
    template_name = str(data.get("custom_template_name", "")).strip()
    numbers = [int(x) for x in data.get("custom_template_numbers", [])]

    if text_value in done_words:
        if not numbers:
            await message.answer(t(lang, "custom_template_need_photo"))
            return
        await upsert_user_template_combo(message.from_user.id, template_name, numbers)
        await upsert_global_template_combo(template_name, numbers, message.from_user.id)
        await add_template_submission_log(message.from_user.id, template_name, numbers)

        if settings.admin_id and settings.admin_id != message.from_user.id:
            try:
                await message.bot.send_message(
                    settings.admin_id,
                    t(
                        "ru",
                        "custom_template_admin_notice",
                        user_id=message.from_user.id,
                        name=template_name,
                        templates=",".join(str(x) for x in numbers),
                    ),
                )
            except Exception:
                logger.warning("Failed to notify admin about template submission")

        await state.clear()
        await message.answer(
            t(lang, "custom_template_created", name=template_name, templates=",".join(str(x) for x in numbers)),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return

    if not message.photo:
        await message.answer(t(lang, "source_invalid_input"))
        return

    template_num = _next_template_number()
    while any((ASSETS_DIR / f"{template_num}{suffix}").exists() for suffix in (".jpg", ".jpeg", ".png")):
        template_num += 1
    output_path = ASSETS_DIR / f"{template_num}.jpg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await message.bot.download(message.photo[-1], destination=str(output_path))
    except Exception:
        await message.answer(t(lang, "build_error", error="template upload failed"))
        return

    numbers.append(template_num)
    await state.update_data(custom_template_numbers=numbers)
    await message.answer(t(lang, "custom_template_photo_saved", template_num=template_num))


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cancel_generation(message: Message, state: FSMContext) -> None:
    await _cleanup_slide_image_temp_dir(state)
    await state.clear()
    lang, _ = await _lang_and_tokens(message)
    await message.answer(
        t(lang, "generation_cancelled"),
        reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
    )


@router.message(Command("language"))
@router.message(F.text.func(lambda value: is_action_text(value, "language")))
async def open_language_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang, _ = await _lang_and_tokens(message)
    await message.answer(t(lang, "choose_language"), reply_markup=build_language_menu(lang))


@router.message(F.text.func(lambda value: detect_language(value) is not None))
async def choose_language(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    selected = detect_language(message.text)
    if selected is None:
        return
    await state.clear()
    await set_user_language(message.from_user.id, selected, settings.default_tokens)
    tokens, _ = await get_user_data(message.from_user.id, settings.default_tokens)
    await message.answer(
        f"{t(selected, 'language_changed')}\n{t(selected, 'tokens_info', tokens=tokens)}",
        reply_markup=build_main_menu(lang=selected, is_admin=_is_admin(message)),
    )


@router.message(Command("admin"))
@router.message(F.text.func(lambda value: is_action_text(value, "admin_panel")))
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    await state.clear()
    await message.answer(t(lang, "admin_panel"), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("premium"))
@router.message(F.text.func(lambda value: is_action_text(value, "premium_section")))
async def open_premium_section(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    lang, _ = await _lang_and_tokens(message)
    allowed = await is_premium_user(message.from_user.id)
    if not allowed:
        await message.answer(t(lang, "premium_section_denied"))
        return
    await state.clear()
    await message.answer(
        f"{t(lang, 'premium_section_opened')}\n\n{t(lang, 'premium_section_hint')}",
        reply_markup=build_premium_menu(lang),
    )


@router.message(F.text.func(lambda value: is_action_text(value, "premium_voice_chat")))
async def premium_voice_button(message: Message) -> None:
    if message.from_user is None:
        return
    lang, _ = await _lang_and_tokens(message)
    allowed = await is_premium_user(message.from_user.id)
    if not allowed:
        await message.answer(t(lang, "premium_section_denied"))
        return
    await message.answer(t(lang, "premium_send_voice_prompt"))


@router.message(F.text.func(lambda value: is_action_text(value, "to_menu")))
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang, _ = await _lang_and_tokens(message)
    await message.answer(t(lang, "main_menu"), reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)))


@router.message(F.text.func(lambda value: is_action_text(value, "issue_tokens")))
async def admin_issue_tokens_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    await state.set_state(AdminForm.target_user_id)
    await message.answer(t(lang, "ask_target_user_id"))


@router.message(AdminForm.target_user_id)
async def admin_issue_tokens_target(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "id_must_number"))
        return
    await state.update_data(target_user_id=int(text))
    await state.set_state(AdminForm.token_amount)
    await message.answer(t(lang, "ask_token_amount"))


@router.message(AdminForm.token_amount)
async def admin_issue_tokens_amount(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not re.fullmatch(r"\d+", text):
        await message.answer(t(lang, "amount_must_int"))
        return
    amount = int(text)
    if amount <= 0:
        await message.answer(t(lang, "amount_gt_zero"))
        return
    data = await state.get_data()
    raw_target_id = data.get("target_user_id")
    if raw_target_id is None:
        await state.clear()
        await message.answer(t(lang, "action_expired_retry"), reply_markup=build_admin_panel_menu(lang))
        return
    try:
        target_user_id = int(raw_target_id)
    except (TypeError, ValueError):
        await state.clear()
        await message.answer(t(lang, "action_expired_retry"), reply_markup=build_admin_panel_menu(lang))
        return
    new_balance = await add_user_tokens(target_user_id, amount, settings.default_tokens)
    await state.clear()
    await message.answer(
        t(lang, "tokens_added", user_id=target_user_id, amount=amount, balance=new_balance),
        reply_markup=build_admin_panel_menu(lang),
    )


@router.message(F.text.func(lambda value: is_action_text(value, "remove_tokens")))
async def admin_remove_tokens_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    await state.set_state(AdminForm.remove_target_user_id)
    await message.answer(t(lang, "ask_remove_target_user_id"))


@router.message(AdminForm.remove_target_user_id)
async def admin_remove_tokens_target(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "id_must_number"))
        return
    await state.update_data(remove_target_user_id=int(text))
    await state.set_state(AdminForm.remove_token_amount)
    await message.answer(t(lang, "ask_remove_token_amount"))


@router.message(AdminForm.remove_token_amount)
async def admin_remove_tokens_amount(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not re.fullmatch(r"\d+", text):
        await message.answer(t(lang, "amount_must_int"))
        return
    amount = int(text)
    if amount <= 0:
        await message.answer(t(lang, "amount_gt_zero"))
        return
    data = await state.get_data()
    raw_target_id = data.get("remove_target_user_id")
    if raw_target_id is None:
        await state.clear()
        await message.answer(t(lang, "action_expired_retry"), reply_markup=build_admin_panel_menu(lang))
        return
    try:
        target_user_id = int(raw_target_id)
    except (TypeError, ValueError):
        await state.clear()
        await message.answer(t(lang, "action_expired_retry"), reply_markup=build_admin_panel_menu(lang))
        return
    new_balance = await remove_user_tokens(target_user_id, amount, settings.default_tokens)
    await state.clear()
    await message.answer(
        t(lang, "tokens_removed", user_id=target_user_id, amount=amount, balance=new_balance),
        reply_markup=build_admin_panel_menu(lang),
    )


@router.message(F.text.func(lambda value: is_action_text(value, "check_tokens")))
async def admin_check_tokens_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    await state.set_state(AdminForm.check_user_id)
    await message.answer(t(lang, "ask_check_user_id"))


@router.message(AdminForm.check_user_id)
async def admin_check_tokens(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "id_must_number"))
        return
    user_id = int(text)
    tokens, _ = await get_user_data(user_id, settings.default_tokens)
    await state.clear()
    await message.answer(
        t(lang, "user_tokens", user_id=user_id, tokens=tokens),
        reply_markup=build_admin_panel_menu(lang),
    )


async def _send_user_profile_card(message: Message, lang: str, user_id: int) -> None:
    profile = await get_user_profile(user_id)
    if profile is None:
        await message.answer(t(lang, "user_profile_not_found", user_id=user_id), reply_markup=build_admin_panel_menu(lang))
        return

    tokens, app_lang = await get_user_data(user_id, settings.default_tokens)
    ban = await get_user_ban(user_id)
    username = f"@{profile.username}" if profile.username else "-"
    raw_user = escape(profile.raw_user_json[:1400] or "")
    raw_chat = escape(profile.raw_chat_json[:1400] or "")
    ban_reason = escape(ban.reason) if ban is not None and ban.reason else "-"

    lines = [
        f"👤 <b>{t(lang, 'user_profile_title', user_id=user_id)}</b>",
        f"<b>id</b>: <code>{profile.telegram_user_id}</code>",
        f"<b>chat_id</b>: <code>{profile.chat_id}</code>",
        f"<b>username</b>: {escape(username)}",
        f"<b>first_name</b>: {escape(profile.first_name or '-')}",
        f"<b>last_name</b>: {escape(profile.last_name or '-')}",
        f"<b>full_name</b>: {escape(profile.full_name or '-')}",
        f"<b>tg_language_code</b>: {escape(profile.language_code or '-')}",
        f"<b>app_language</b>: {escape(app_lang)}",
        f"<b>tokens</b>: {tokens}",
        f"<b>is_bot</b>: {_bool_label(profile.is_bot)}",
        f"<b>is_premium</b>: {_bool_label(profile.is_premium)}",
        f"<b>added_to_attachment_menu</b>: {_bool_label(profile.added_to_attachment_menu)}",
        f"<b>can_join_groups</b>: {_bool_label(profile.can_join_groups)}",
        f"<b>can_read_all_group_messages</b>: {_bool_label(profile.can_read_all_group_messages)}",
        f"<b>supports_inline_queries</b>: {_bool_label(profile.supports_inline_queries)}",
        f"<b>can_connect_to_business</b>: {_bool_label(profile.can_connect_to_business)}",
        f"<b>has_main_web_app</b>: {_bool_label(profile.has_main_web_app)}",
        f"<b>last_message_type</b>: {escape(profile.last_message_type)}",
        f"<b>last_message_text</b>: {escape(profile.last_message_text)}",
        f"<b>last_state</b>: {escape(profile.last_state_name or '-')}",
        f"<b>first_seen</b>: {profile.first_seen_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"<b>last_seen</b>: {profile.last_seen_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"<b>banned</b>: {'yes' if ban is not None else 'no'}",
        f"<b>ban_reason</b>: {ban_reason}",
        f"<b>raw_user_json (first 1400 chars)</b>:\n<code>{raw_user}</code>",
        f"<b>raw_chat_json (first 1400 chars)</b>:\n<code>{raw_chat}</code>",
    ]
    await _send_chunked_html(message, lines)
    await message.answer(t(lang, "admin_panel"), reply_markup=build_admin_panel_menu(lang))


async def _broadcast_text(message: Message, text_value: str, lang: str) -> None:
    await message.answer(t(lang, "broadcast_started"))
    user_ids = await get_broadcast_user_ids(limit=10000)
    sent = 0
    failed = 0
    for index, user_id in enumerate(user_ids, start=1):
        try:
            await message.bot.send_message(chat_id=user_id, text=text_value)
            sent += 1
        except Exception:
            failed += 1
        if index % 40 == 0:
            await asyncio.sleep(0)
    await message.answer(
        t(lang, "broadcast_finished", sent=sent, failed=failed, total=len(user_ids)),
        reply_markup=build_admin_panel_menu(lang),
    )


@router.message(Command("user_profile"))
@router.message(F.text.func(lambda value: is_action_text(value, "user_profile")))
async def admin_user_profile_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    target_user_id = _extract_command_user_id(message)
    if target_user_id is not None:
        await state.clear()
        await _send_user_profile_card(message, lang, target_user_id)
        return
    await state.set_state(AdminForm.profile_user_id)
    await message.answer(t(lang, "ask_profile_user_id"))


@router.message(AdminForm.profile_user_id)
async def admin_user_profile_by_state(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "id_must_number"))
        return
    await state.clear()
    await _send_user_profile_card(message, lang, int(text))


@router.message(Command("ban"))
@router.message(F.text.func(lambda value: is_action_text(value, "ban_user")))
async def admin_ban_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    target_user_id, reason_tail = _extract_command_user_id_and_tail(message)
    if target_user_id is not None:
        reason = reason_tail or t(lang, "ban_default_reason")
        created = await set_user_ban(target_user_id, reason, message.from_user.id if message.from_user else 0)
        key = "user_banned" if created else "user_ban_updated"
        await state.clear()
        await message.answer(t(lang, key, user_id=target_user_id), reply_markup=build_admin_panel_menu(lang))
        return
    await state.set_state(AdminForm.ban_target_user_id)
    await message.answer(t(lang, "ask_ban_user_id"))


@router.message(AdminForm.ban_target_user_id)
async def admin_ban_target(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "id_must_number"))
        return
    await state.update_data(ban_target_user_id=int(text))
    await state.set_state(AdminForm.ban_reason)
    await message.answer(t(lang, "ask_ban_reason"))


@router.message(AdminForm.ban_reason)
async def admin_ban_reason(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    data = await state.get_data()
    raw_target = data.get("ban_target_user_id")
    if raw_target is None:
        await state.clear()
        await message.answer(t(lang, "action_expired_retry"), reply_markup=build_admin_panel_menu(lang))
        return
    reason = (message.text or "").strip()
    if not reason or reason == "-":
        reason = t(lang, "ban_default_reason")
    target_user_id = int(raw_target)
    created = await set_user_ban(target_user_id, reason, message.from_user.id if message.from_user else 0)
    key = "user_banned" if created else "user_ban_updated"
    await state.clear()
    await message.answer(t(lang, key, user_id=target_user_id), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("unban"))
@router.message(F.text.func(lambda value: is_action_text(value, "unban_user")))
async def admin_unban_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    target_user_id = _extract_command_user_id(message)
    if target_user_id is not None:
        removed = await remove_user_ban(target_user_id)
        key = "user_unbanned" if removed else "user_not_banned"
        await state.clear()
        await message.answer(t(lang, key, user_id=target_user_id), reply_markup=build_admin_panel_menu(lang))
        return
    await state.set_state(AdminForm.unban_target_user_id)
    await message.answer(t(lang, "ask_unban_user_id"))


@router.message(AdminForm.unban_target_user_id)
async def admin_unban_target(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "id_must_number"))
        return
    target_user_id = int(text)
    removed = await remove_user_ban(target_user_id)
    key = "user_unbanned" if removed else "user_not_banned"
    await state.clear()
    await message.answer(t(lang, key, user_id=target_user_id), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("broadcast"))
@router.message(F.text.func(lambda value: is_action_text(value, "broadcast_all")))
async def admin_broadcast_start(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[0].startswith("/"):
        await state.clear()
        await _broadcast_text(message, parts[1], lang)
        return
    await state.set_state(AdminForm.broadcast_text)
    await message.answer(t(lang, "broadcast_prompt"))


@router.message(AdminForm.broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text_value = (message.text or "").strip()
    if not text_value:
        await message.answer(t(lang, "source_invalid_input"))
        return
    await state.clear()
    await _broadcast_text(message, text_value, lang)


@router.message(Command("all_users"))
@router.message(F.text.func(lambda value: is_action_text(value, "all_users")))
async def admin_all_users(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return

    profiles = await get_all_user_profiles(limit=1000)
    if not profiles:
        await message.answer(t(lang, "all_users_empty"), reply_markup=build_admin_panel_menu(lang))
        return

    balances = await get_all_users()
    balance_map = {row.telegram_user_id: row for row in balances}

    lines = [f"👥 <b>{t(lang, 'all_users_profiles_title', count=len(profiles))}</b>"]
    for user in profiles:
        balance = balance_map.get(user.telegram_user_id)
        app_lang = balance.language if balance is not None else "-"
        tokens = balance.tokens if balance is not None else 0
        username = f"@{user.username}" if user.username else "-"
        seen = user.last_seen_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"<b>ID</b>: <code>{user.telegram_user_id}</code> | chat=<code>{user.chat_id}</code>\n"
            f"<b>username</b>: {escape(username)} | <b>full_name</b>: {escape(user.full_name or '-')}\n"
            f"<b>first_name</b>: {escape(user.first_name or '-')} | <b>last_name</b>: {escape(user.last_name or '-')}\n"
            f"<b>tg_lang</b>: {escape(user.language_code or '-')} | <b>app_lang</b>: {escape(app_lang)} | <b>tokens</b>: {tokens}\n"
            f"<b>is_premium</b>: {_bool_label(user.is_premium)} | <b>is_bot</b>: {_bool_label(user.is_bot)}\n"
            f"<b>attach_menu</b>: {_bool_label(user.added_to_attachment_menu)} | <b>inline</b>: {_bool_label(user.supports_inline_queries)}\n"
            f"<b>can_join_groups</b>: {_bool_label(user.can_join_groups)} | <b>read_all_groups</b>: {_bool_label(user.can_read_all_group_messages)}\n"
            f"<b>business</b>: {_bool_label(user.can_connect_to_business)} | <b>main_web_app</b>: {_bool_label(user.has_main_web_app)}\n"
            f"<b>last_message_type</b>: {escape(user.last_message_type)} | <b>last_state</b>: {escape(user.last_state_name or '-')}\n"
            f"<b>last_seen</b>: {seen}"
        )
    await _send_chunked_html(message, lines)
    await message.answer(t(lang, "admin_panel"), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("template_requests"))
@router.message(F.text.func(lambda value: is_action_text(value, "template_requests")))
async def admin_template_requests(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return

    rows = await get_recent_template_submissions(limit=100)
    if not rows:
        await message.answer(t(lang, "template_requests_empty"), reply_markup=build_admin_panel_menu(lang))
        return

    lines = [f"🖼 <b>{t(lang, 'template_requests_title', count=len(rows))}</b>"]
    for row in rows:
        created = row.created_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"<b>#{row.id}</b> | {created}\n"
            f"user=<code>{row.telegram_user_id}</code>\n"
            f"name={escape(row.combo_name)}\n"
            f"templates={escape(row.templates_csv)}"
        )
    await _send_chunked_html(message, lines)
    await message.answer(t(lang, "admin_panel"), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("event_logs"))
@router.message(F.text.func(lambda value: is_action_text(value, "event_logs")))
async def admin_event_logs(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return

    events = await get_recent_user_events(limit=100)
    if not events:
        await message.answer(t(lang, "event_logs_empty"), reply_markup=build_admin_panel_menu(lang))
        return

    lines = [f"📝 <b>{t(lang, 'event_logs_title', count=len(events))}</b>"]
    for event in events:
        created = event.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        username = f"@{event.username}" if event.username else "no_username"
        text_payload = escape(event.message_text or "")
        lines.append(
            f"<b>{created}</b> | <code>{event.telegram_user_id}</code> ({escape(username)})\n"
            f"type={escape(event.message_type)} state={escape(event.state_name or '-')}\n"
            f"{text_payload}"
        )
    await _send_chunked_html(message, lines)
    await message.answer(t(lang, "admin_panel"), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("premium_add"))
@router.message(F.text.func(lambda value: is_action_text(value, "premium_add")))
async def admin_premium_add(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    target_user_id = _extract_command_user_id(message)
    if target_user_id is None:
        await message.answer(t(lang, "premium_add_usage"), reply_markup=build_admin_panel_menu(lang))
        return
    added = await set_premium_user(
        user_id=target_user_id,
        assigned_by_user_id=message.from_user.id if message.from_user else 0,
    )
    key = "premium_added" if added else "premium_already"
    await message.answer(t(lang, key, user_id=target_user_id), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("premium_remove"))
@router.message(F.text.func(lambda value: is_action_text(value, "premium_remove")))
async def admin_premium_remove(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    target_user_id = _extract_command_user_id(message)
    if target_user_id is None:
        await message.answer(t(lang, "premium_remove_usage"), reply_markup=build_admin_panel_menu(lang))
        return
    removed = await remove_premium_user(target_user_id)
    key = "premium_removed" if removed else "premium_not_found"
    await message.answer(t(lang, key, user_id=target_user_id), reply_markup=build_admin_panel_menu(lang))


@router.message(Command("premium_list"))
@router.message(F.text.func(lambda value: is_action_text(value, "premium_list")))
async def admin_premium_list(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return
    users = await get_premium_users(limit=200)
    if not users:
        await message.answer(t(lang, "premium_list_empty"), reply_markup=build_admin_panel_menu(lang))
        return
    lines = [f"⭐ <b>{t(lang, 'premium_list_title', count=len(users))}</b>"]
    for row in users:
        created = row.created_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"<code>{row.telegram_user_id}</code> | by=<code>{row.assigned_by_user_id}</code> | {created}"
        )
    await _send_chunked_html(message, lines)
    await message.answer(t(lang, "admin_panel"), reply_markup=build_admin_panel_menu(lang))


@router.message(StateFilter(None), F.voice)
async def premium_voice_chat(message: Message) -> None:
    if message.from_user is None:
        return

    lang, _ = await _lang_and_tokens(message)
    allowed = await is_premium_user(message.from_user.id)
    if not allowed:
        await message.answer(t(lang, "premium_only_voice"))
        return

    if not settings.openrouter_api_key.strip():
        await message.answer(t(lang, "premium_missing_openrouter_key"))
        return

    await message.answer(t(lang, "premium_voice_processing"))

    temp_file_path: Path | None = None
    temp_dir: Path | None = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="tg_voice_"))
        temp_file_path = temp_dir / f"{message.voice.file_id}.ogg"
        await message.bot.download(message.voice, destination=str(temp_file_path))

        try:
            transcribed_text = await transcribe_voice_file(temp_file_path, lang=lang)
        except Exception:
            logger.exception("Voice transcription failed")
            await message.answer(t(lang, "premium_transcription_failed"))
            return

        await _send_chunked_plain(message, t(lang, "premium_voice_transcript", text=transcribed_text))

        try:
            ai_answer = await ask_openrouter_from_text(transcribed_text, lang=lang)
        except Exception:
            logger.exception("OpenRouter reply failed")
            await message.answer(t(lang, "premium_ai_failed"))
            return

        await _send_chunked_plain(message, t(lang, "premium_voice_answer", text=ai_answer))
    finally:
        if temp_file_path is not None:
            try:
                temp_file_path.unlink(missing_ok=True)
            except Exception:
                pass
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.message(Command("presentation"))
@router.message(F.text.func(lambda value: is_action_text(value, "create_presentation")))
async def start_presentation_generation(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    lang, _ = await _lang_and_tokens(message)

    await _cleanup_slide_image_temp_dir(state)
    await state.clear()
    await state.set_state(PresentationForm.slide_count)
    await message.answer(
        t(lang, "ask_slide_count"),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(PresentationForm.slide_count)
async def process_slide_count(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "slide_count_number"))
        return

    count = int(text)
    if count < 1 or count > 30:
        await message.answer(t(lang, "slide_count_range"))
        return

    available = list_presentation_types()
    if not available:
        await state.clear()
        await message.answer(
            t(lang, "no_templates"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return

    if message.from_user is None:
        await state.clear()
        return

    global_combos = await get_global_template_combos()
    user_combos = await get_user_template_combos(message.from_user.id)
    combo_options: dict[str, list[int]] = {}
    combo_names: dict[str, str] = {}
    combo_groups: dict[str, list[str]] = {"default": [], "global": [], "my": []}
    index = 1

    for combo_name, combo_seq in _default_combos(sorted(available), lang):
        key = f"d{index}"
        combo_options[key] = combo_seq
        combo_names[key] = combo_name
        combo_groups["default"].append(key)
        index += 1

    for global_combo in global_combos:
        combo_seq = _normalize_template_sequence(global_combo.templates_csv, set(available))
        if not combo_seq:
            continue
        key = f"g{global_combo.id}"
        combo_options[key] = combo_seq
        combo_names[key] = f"[GLOBAL] {global_combo.name}"
        combo_groups["global"].append(key)
        index += 1

    for user_combo in user_combos:
        combo_seq = _normalize_template_sequence(user_combo.templates_csv, set(available))
        if not combo_seq:
            continue
        key = f"m{user_combo.id}"
        combo_options[key] = combo_seq
        combo_names[key] = f"[MY] {user_combo.name}"
        combo_groups["my"].append(key)
        index += 1

    active_tab = next((tab for tab in _combo_tab_order() if combo_groups.get(tab)), "default")
    active_page = 0
    keyboard = _build_combo_keyboard(
        lang=lang,
        combo_groups=combo_groups,
        combo_options=combo_options,
        combo_names=combo_names,
        active_tab=active_tab,
        active_page=active_page,
    )
    caption = _build_combo_caption(
        lang=lang,
        combo_groups=combo_groups,
        combo_options=combo_options,
        active_tab=active_tab,
        active_page=active_page,
        available=sorted(available),
    )

    await state.update_data(
        slide_count=count,
        combo_options=combo_options,
        combo_names=combo_names,
        combo_groups=combo_groups,
        combo_active_tab=active_tab,
        combo_active_page=active_page,
        template_types=[],
    )
    await state.set_state(PresentationForm.template_type)
    await message.answer(caption, reply_markup=keyboard)



@router.callback_query(PresentationForm.template_type, F.data.startswith("cmb:"))
async def process_template_combo_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    if callback.data is None:
        await callback.answer()
        return

    lang = "ru"
    if callback.from_user is not None:
        _, lang = await get_user_data(callback.from_user.id, settings.default_tokens)

    data = await state.get_data()
    combo_options: dict[str, list[int]] = dict(data.get("combo_options", {}))
    combo_names: dict[str, str] = dict(data.get("combo_names", {}))
    combo_groups: dict[str, list[str]] = dict(data.get("combo_groups", {}))
    available = sorted(list_presentation_types())

    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer()
        return

    action = parts[1]
    active_tab = str(data.get("combo_active_tab", "default"))
    active_page = int(data.get("combo_active_page", 0))

    if action == "noop":
        await callback.answer()
        return

    if action == "tab" and len(parts) == 3:
        tab = parts[2]
        if tab in combo_groups and combo_groups.get(tab):
            active_tab = tab
            active_page = 0
            await state.update_data(combo_active_tab=active_tab, combo_active_page=active_page)
        keyboard = _build_combo_keyboard(lang, combo_groups, combo_options, combo_names, active_tab, active_page)
        caption = _build_combo_caption(lang, combo_groups, combo_options, active_tab, active_page, available)
        try:
            await callback.message.edit_text(caption, reply_markup=keyboard)
        except Exception:
            pass
        await callback.answer()
        return

    if action == "page" and len(parts) == 3 and parts[2].isdigit():
        active_page = int(parts[2])
        await state.update_data(combo_active_tab=active_tab, combo_active_page=active_page)
        keyboard = _build_combo_keyboard(lang, combo_groups, combo_options, combo_names, active_tab, active_page)
        caption = _build_combo_caption(lang, combo_groups, combo_options, active_tab, active_page, available)
        try:
            await callback.message.edit_text(caption, reply_markup=keyboard)
        except Exception:
            pass
        await callback.answer()
        return

    if action == "sel" and len(parts) == 3:
        key = parts[2]
        slide_count = int(data.get("slide_count", 0))
        if slide_count <= 0 or key not in combo_options:
            await callback.answer(t(lang, "combo_pick_number"), show_alert=False)
            return
        template_types = _expand_combo(combo_options[key], slide_count)
        await state.update_data(template_types=template_types)
        await state.set_state(PresentationForm.font_name)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            t(lang, "combo_selected", name=escape(combo_names.get(key, "Combo")))
        )
        await callback.message.answer(t(lang, "ask_font"), reply_markup=build_font_menu())
        await callback.answer()
        return

    await callback.answer()


@router.message(PresentationForm.template_type)
async def process_template_type(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()

    if text.lower() in ("cancel", "отмена", "bekor"):
        if message.from_user is None:
            await state.clear()
            return
        await state.set_state(PresentationForm.slide_count)
        await message.answer(t(lang, "ask_slide_count"))
        return

    data = await state.get_data()
    raw_slide_count = data.get("slide_count")
    if raw_slide_count is None:
        await state.clear()
        await message.answer(
            t(lang, "flow_expired_restart"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return
    try:
        slide_count = int(raw_slide_count)
    except (TypeError, ValueError):
        await state.clear()
        await message.answer(
            t(lang, "flow_expired_restart"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return
    combo_options: dict[str, list[int]] = dict(data.get("combo_options", {}))
    combo_names: dict[str, str] = dict(data.get("combo_names", {}))
    available_set = set(list_presentation_types())

    if text.casefold().startswith("new "):
        if message.from_user is None:
            await state.clear()
            return
        payload = text[4:].strip()
        if ":" not in payload:
            await message.answer(t(lang, "combo_new_format"))
            return
        name_part, seq_part = payload.split(":", 1)
        combo_name = name_part.strip()
        if len(combo_name) < 2:
            await message.answer(t(lang, "combo_name_short"))
            return
        combo_seq = _normalize_template_sequence(seq_part, available_set)
        if not combo_seq:
            await message.answer(t(lang, "combo_invalid_sequence"))
            return
        await upsert_user_template_combo(message.from_user.id, combo_name, combo_seq)
        template_types = _expand_combo(combo_seq, slide_count)
        await state.update_data(template_types=template_types)
        await message.answer(t(lang, "combo_saved", name=combo_name))
        await state.set_state(PresentationForm.font_name)
        await message.answer(t(lang, "ask_font"), reply_markup=build_font_menu())
        return

    selected_key = text
    if text.isdigit():
        digit = int(text)
        default_keys = combo_options.keys()
        selected_key = f"d{digit}" if f"d{digit}" in default_keys else text

    if selected_key not in combo_options:
        await message.answer(t(lang, "combo_pick_number"))
        return

    template_types = _expand_combo(combo_options[selected_key], slide_count)
    await state.update_data(template_types=template_types)
    if selected_key in combo_names:
        await message.answer(t(lang, "combo_selected", name=escape(combo_names[selected_key])))
    await state.set_state(PresentationForm.font_name)
    await message.answer(t(lang, "ask_font"), reply_markup=build_font_menu())




@router.message(PresentationForm.font_name)
async def process_font_name(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    font_name = (message.text or "").strip()
    if len(font_name) < 2:
        await message.answer(t(lang, "invalid_font"))
        return
    await state.update_data(font_name=font_name)
    await state.set_state(PresentationForm.font_color)
    await message.answer(t(lang, "ask_color"), reply_markup=build_color_menu(lang))


@router.message(PresentationForm.font_color)
async def process_font_color(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    parsed = color_hex_by_text(message.text)
    if parsed is None:
        await message.answer(t(lang, "invalid_color"), reply_markup=build_color_menu(lang))
        return
    color_hex, color_name = parsed
    await state.update_data(font_color=color_hex, font_color_label=color_name)
    await state.set_state(PresentationForm.topic)
    await message.answer(t(lang, "ask_topic"), reply_markup=ReplyKeyboardRemove())


@router.message(PresentationForm.topic)
async def process_topic(message: Message, state: FSMContext) -> None:
    topic = (message.text or "").strip()
    if message.from_user is None:
        await state.clear()
        return
    lang, _ = await _lang_and_tokens(message)
    if len(topic) < 3:
        await message.answer(t(lang, "topic_short"))
        return

    await state.update_data(topic=topic)
    await state.set_state(PresentationForm.source_material)
    await message.answer(t(lang, "ask_source_material"))


@router.message(PresentationForm.source_material)
async def process_source_material(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await state.clear()
        return

    lang, _ = await _lang_and_tokens(message)
    source_text: str | None = None
    text_value = (message.text or "").strip()
    skip_words = _skip_words()

    temp_file_path: Path | None = None
    temp_dir: Path | None = None

    try:
        if message.document is not None:
            if message.document.file_size and message.document.file_size > MAX_DOWNLOAD_BYTES:
                await message.answer(t(lang, "source_file_too_large"))
                return
            if message.document.file_name:
                ext = Path(message.document.file_name).suffix.lower()
                if ext not in SUPPORTED_TEXT_EXTENSIONS:
                    await message.answer(
                        t(
                            lang,
                            "source_file_type_unsupported",
                            exts=", ".join(sorted(SUPPORTED_TEXT_EXTENSIONS)),
                        )
                    )
                    return
            temp_dir = Path(tempfile.mkdtemp(prefix="tg_source_"))
            filename = message.document.file_name or "source.txt"
            temp_file_path = temp_dir / filename
            await message.bot.download(message.document, destination=str(temp_file_path))
            try:
                source_text = await asyncio.to_thread(extract_text_from_file, temp_file_path)
            except ValueError as exc:
                if str(exc) == "file_too_large":
                    await message.answer(t(lang, "source_file_too_large"))
                elif str(exc) == "unsupported_file_type":
                    await message.answer(
                        t(
                            lang,
                            "source_file_type_unsupported",
                            exts=", ".join(sorted(SUPPORTED_TEXT_EXTENSIONS)),
                        )
                    )
                else:
                    await message.answer(t(lang, "source_invalid_input"))
                return
        elif text_value:
            if text_value.casefold() in skip_words:
                source_text = None
            elif is_http_url(text_value):
                try:
                    source_text = await asyncio.to_thread(extract_text_from_url, text_value)
                except ValueError:
                    await message.answer(t(lang, "source_url_fetch_error"))
                    return
            else:
                source_text = normalize_source_text(text_value)
        else:
            await message.answer(t(lang, "source_invalid_input"))
            return

        await state.update_data(source_material=source_text)
        await state.set_state(PresentationForm.creator_names)
        await message.answer(t(lang, "ask_creator_names"))
    finally:
        if temp_file_path is not None:
            try:
                temp_file_path.unlink(missing_ok=True)
            except Exception:
                pass
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.message(PresentationForm.creator_names)
async def process_creator_names(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await state.clear()
        return

    lang, _ = await _lang_and_tokens(message)
    text_value = (message.text or "").strip()
    skip_words = _skip_words()
    creator_names = None if text_value.casefold() in skip_words else text_value[:300]

    data = await state.get_data()
    slide_count = int(data.get("slide_count", 0))
    if slide_count <= 0:
        logger.warning("Slide count missing before image upload step for user %s", message.from_user.id)
        await _cleanup_slide_image_temp_dir(state)
        await state.clear()
        await message.answer(
            t(lang, "flow_expired_restart"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return

    await state.update_data(
        creator_names=creator_names,
        slide_image_paths=[],
        slide_images_temp_dir=None,
    )
    await state.set_state(PresentationForm.slide_images)
    await message.answer(t(lang, "ask_slide_images", max_count=slide_count * 2))


@router.message(PresentationForm.slide_images)
async def process_slide_images(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await _cleanup_slide_image_temp_dir(state)
        await state.clear()
        return

    lang, _ = await _lang_and_tokens(message)
    data = await state.get_data()
    slide_count = int(data.get("slide_count", 0))
    max_image_count = max(2, slide_count * 2)
    if slide_count <= 0:
        await _cleanup_slide_image_temp_dir(state)
        await state.clear()
        await message.answer(
            t(lang, "flow_expired_restart"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return

    stored_paths = [str(x) for x in data.get("slide_image_paths", []) if isinstance(x, str)]
    text_value = (message.text or "").strip()
    lowered = text_value.casefold()
    if lowered in _skip_words():
        stored_paths = []
        await state.update_data(slide_image_paths=stored_paths)
        await _finalize_presentation_generation(message, state, lang)
        return
    if lowered in _done_words():
        await _finalize_presentation_generation(message, state, lang)
        return

    file_size = 0
    file_suffix = ".jpg"
    if message.photo:
        file_size = int(message.photo[-1].file_size or 0)
    elif message.document is not None:
        filename = (message.document.file_name or "").lower()
        file_suffix = Path(filename).suffix.lower() or ".jpg"
        if file_suffix not in _extract_supported_image_document_exts():
            await message.answer(
                t(
                    lang,
                    "slide_images_file_type_unsupported",
                    exts=", ".join(_extract_supported_image_document_exts()),
                )
            )
            return
        file_size = int(message.document.file_size or 0)
    else:
        await message.answer(t(lang, "slide_images_invalid_input"))
        return

    if file_size > MAX_CUSTOM_SLIDE_IMAGE_BYTES:
        await message.answer(t(lang, "slide_images_file_too_large"))
        return

    if len(stored_paths) >= max_image_count:
        await message.answer(t(lang, "slide_images_limit_reached", max_count=max_image_count))
        await _finalize_presentation_generation(message, state, lang)
        return

    temp_dir_raw = data.get("slide_images_temp_dir")
    if isinstance(temp_dir_raw, str) and temp_dir_raw.strip():
        temp_dir = Path(temp_dir_raw)
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="tg_slide_images_"))
        await state.update_data(slide_images_temp_dir=str(temp_dir))

    destination = temp_dir / f"slide_image_{len(stored_paths)+1}{file_suffix}"
    try:
        source = message.photo[-1] if message.photo else message.document
        await message.bot.download(source, destination=str(destination))
        with Image.open(destination) as image:
            width, height = image.size
            if width < MIN_CUSTOM_SLIDE_IMAGE_WIDTH or height < MIN_CUSTOM_SLIDE_IMAGE_HEIGHT:
                destination.unlink(missing_ok=True)
                await message.answer(
                    t(
                        lang,
                        "slide_images_too_small",
                        min_w=MIN_CUSTOM_SLIDE_IMAGE_WIDTH,
                        min_h=MIN_CUSTOM_SLIDE_IMAGE_HEIGHT,
                    )
                )
                return
    except Exception:
        destination.unlink(missing_ok=True)
        await message.answer(t(lang, "slide_images_download_failed"))
        return

    stored_paths.append(str(destination))
    await state.update_data(slide_image_paths=stored_paths)
    await message.answer(
        t(
            lang,
            "slide_images_photo_saved",
            current=len(stored_paths),
            max_count=max_image_count,
        )
    )

    if len(stored_paths) >= max_image_count:
        await message.answer(t(lang, "slide_images_limit_reached", max_count=max_image_count))
        await _finalize_presentation_generation(message, state, lang)
