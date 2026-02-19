from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message, ReplyKeyboardRemove

from bot.config import load_settings
from bot.db import (
    add_presentation_history,
    add_template_submission_log,
    add_user_tokens,
    get_all_users,
    get_global_template_combos,
    get_recent_user_events,
    get_recent_template_submissions,
    get_user_data,
    get_user_presentation_history,
    get_user_template_combos,
    remove_user_tokens,
    set_user_language,
    try_spend_user_token,
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
)
from bot.services.ai_text_presentation_generator import generate_slide_content, list_presentation_types
from bot.services.presentation_builder import build_presentation_file
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
}


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
    names = {
        "ru": {
            "all": "Все шаблоны по кругу",
            "forward": "Классика по возрастанию",
            "reverse": "Контраст по убыванию",
            "odd_even": "Нечетные + четные",
        },
        "en": {
            "all": "All templates loop",
            "forward": "Classic ascending",
            "reverse": "Contrast descending",
            "odd_even": "Odd + even",
        },
        "uz": {
            "all": "Barcha shablonlar aylana",
            "forward": "Klassik o'sish",
            "reverse": "Kamayish kontrasti",
            "odd_even": "Toq + juft",
        },
    }
    local = names.get(lang, names["ru"])
    forward = available[:]
    reverse = list(reversed(available))
    odd_even = [item for item in available if item % 2 == 1] + [item for item in available if item % 2 == 0]
    return [
        (local["all"], available[:]),
        (local["forward"], forward),
        (local["reverse"], reverse),
        (local["odd_even"], odd_even or available[:]),
    ]


async def send_template_preview(message: Message, template_num: int, lang: str, color: str = None) -> None:
    if color and template_num <= 10:
        color_map = {"blue": "", "purple": "_purple", "red": "_red", "orange": "_orange", "green": "_green"}
        color_suffix = color_map.get(color.lower(), "")
        template_path = ASSETS_DIR / f"{template_num}{color_suffix}.png"
    else:
        template_path = ASSETS_DIR / f"{template_num}.png"
    
    if template_path.exists():
        photo = FSInputFile(str(template_path))
        template_name = TEMPLATE_NAMES.get(template_num, f"Template {template_num}")
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


class AdminForm(StatesGroup):
    target_user_id = State()
    token_amount = State()
    remove_target_user_id = State()
    remove_token_amount = State()
    check_user_id = State()


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
                        "\n".join(f"#{num}. {TEMPLATE_NAMES.get(num, f'Template {num}')}" 
                                 for num in sorted(available)),
                        parse_mode="HTML")
    
    ordered = sorted(available)
    preview_numbers = ordered[:3] + [item for item in ordered[-3:] if item not in ordered[:3]]
    for template_num in preview_numbers:
        await send_template_preview(message, template_num, lang)
        await message.answer("➖")


@router.message(F.text.func(lambda value: is_action_text(value, "about")))
async def about_bot(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    await message.answer(t(lang, "about"))


@router.message(Command("tokens"))
async def my_tokens(message: Message) -> None:
    lang, tokens = await _lang_and_tokens(message)
    await message.answer(t(lang, "my_tokens", tokens=tokens))


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
    target_user_id = int(data["target_user_id"])
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
    target_user_id = int(data["remove_target_user_id"])
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


@router.message(Command("all_users"))
@router.message(F.text.func(lambda value: is_action_text(value, "all_users")))
async def admin_all_users(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    if not _is_admin(message):
        await message.answer(t(lang, "access_denied"))
        return

    users = await get_all_users()
    if not users:
        await message.answer(t(lang, "all_users_empty"), reply_markup=build_admin_panel_menu(lang))
        return

    labels = {
        "ru": ("Пользователь", "Токены", "Язык"),
        "en": ("User", "Tokens", "Language"),
        "uz": ("Foydalanuvchi", "Token", "Til"),
    }
    user_label, token_label, lang_label = labels.get(lang, labels["ru"])
    lines = [f"👥 <b>{t(lang, 'all_users_title', count=len(users))}</b>"]
    for user in users:
        lines.append(
            f"<b>{user_label}</b>: <code>{user.telegram_user_id}</code> | "
            f"<b>{token_label}</b>: {user.tokens} | "
            f"<b>{lang_label}</b>: {escape(user.language)}"
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


@router.message(Command("presentation"))
@router.message(F.text.func(lambda value: is_action_text(value, "create_presentation")))
async def start_presentation_generation(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    lang, tokens = await _lang_and_tokens(message)
    if tokens <= 0:
        await message.answer(
            t(lang, "no_tokens"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return

    await state.clear()
    await state.set_state(PresentationForm.slide_count)
    await message.answer(
        t(lang, "ask_slide_count", tokens=tokens),
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
    options: dict[str, list[int]] = {}
    lines = [t(lang, "choose_combo_title")]
    index = 1

    for combo_name, combo_seq in _default_combos(sorted(available), lang):
        options[str(index)] = combo_seq
        lines.append(f"{index}. {combo_name}: {','.join(str(x) for x in combo_seq)}")
        index += 1

    for global_combo in global_combos:
        combo_seq = _normalize_template_sequence(global_combo.templates_csv, set(available))
        if not combo_seq:
            continue
        options[str(index)] = combo_seq
        lines.append(f"{index}. [GLOBAL] {escape(global_combo.name)}: {','.join(str(x) for x in combo_seq)}")
        index += 1

    for user_combo in user_combos:
        combo_seq = _normalize_template_sequence(user_combo.templates_csv, set(available))
        if not combo_seq:
            continue
        options[str(index)] = combo_seq
        lines.append(f"{index}. [MY] {escape(user_combo.name)}: {','.join(str(x) for x in combo_seq)}")
        index += 1

    await state.update_data(slide_count=count, combo_options=options, template_types=[])
    await state.set_state(PresentationForm.template_type)
    await message.answer("\n".join(lines))
    await message.answer(
        t(lang, "choose_combo_hint", available=", ".join(str(x) for x in sorted(available))),
        reply_markup=ReplyKeyboardRemove(),
    )



@router.message(PresentationForm.template_type)
async def process_template_type(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()

    if text.lower() in ("cancel", "отмена", "bekor"):
        await state.set_state(PresentationForm.slide_count)
        await message.answer(
            t(lang, "ask_slide_count", tokens=(await get_user_data(message.from_user.id, settings.default_tokens))[0])
        )
        return

    data = await state.get_data()
    slide_count = int(data["slide_count"])
    combo_options: dict[str, list[int]] = dict(data.get("combo_options", {}))
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

    if text not in combo_options:
        await message.answer(t(lang, "combo_pick_number"))
        return

    template_types = _expand_combo(combo_options[text], slide_count)
    await state.update_data(template_types=template_types)
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
    skip_words = {"skip", "пропустить", "нет", "yoq", "yo'q", "o'tkazib yuborish"}

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

        data = await state.get_data()
        topic = str(data["topic"])
        slide_count = int(data["slide_count"])
        template_types = [int(x) for x in data.get("template_types", [])]
        font_name = str(data["font_name"])
        font_color = str(data["font_color"])
        font_color_label = str(data["font_color_label"])

        ok, tokens_left = await try_spend_user_token(message.from_user.id, settings.default_tokens)
        if not ok:
            await state.clear()
            await message.answer(
                t(lang, "no_tokens"),
                reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
            )
            return

        await message.answer(t(lang, "generating"))

        file_path: Path | None = None
        restore_token = True
        try:
            slides = await generate_slide_content(
                topic=topic,
                slide_count=slide_count,
                template_type=template_types[0] if template_types else 1,
                lang=lang,
                source_material=source_text,
            )
            file_path = await build_presentation_file(
                topic=topic,
                template_types=template_types,
                slides=slides,
                font_name=font_name,
                font_color=font_color,
            )
            await add_presentation_history(
                user_id=message.from_user.id,
                topic=topic,
                slide_count=slide_count,
                template_types=template_types,
                font_name=font_name,
                font_color=font_color,
                language=lang,
            )
            restore_token = False
            await message.answer_document(
                document=FSInputFile(file_path),
                caption=t(
                    lang,
                    "ready",
                    slides=slide_count,
                    font=font_name,
                    color=font_color_label,
                    tokens=tokens_left,
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
            if restore_token:
                await add_user_tokens(message.from_user.id, 1, settings.default_tokens)
            if file_path is not None:
                shutil.rmtree(file_path.parent, ignore_errors=True)
            await state.clear()
    finally:
        if temp_file_path is not None:
            try:
                temp_file_path.unlink(missing_ok=True)
            except Exception:
                pass
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
