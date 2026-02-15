from __future__ import annotations

import logging
import re
import shutil
from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message, ReplyKeyboardRemove

from bot.config import load_settings
from bot.db import add_user_tokens, get_user_data, set_user_language, try_spend_user_token
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

logger = logging.getLogger(__name__)
router = Router()
settings = load_settings()


class PresentationForm(StatesGroup):
    slide_count = State()
    template_type = State()
    font_name = State()
    font_color = State()
    topic = State()


class AdminForm(StatesGroup):
    target_user_id = State()
    token_amount = State()
    check_user_id = State()


def _is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == settings.admin_id)


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


@router.message(F.text.func(lambda value: is_action_text(value, "about")))
async def about_bot(message: Message) -> None:
    lang, _ = await _lang_and_tokens(message)
    await message.answer(t(lang, "about"))


@router.message(Command("tokens"))
async def my_tokens(message: Message) -> None:
    lang, tokens = await _lang_and_tokens(message)
    await message.answer(t(lang, "my_tokens", tokens=tokens))


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

    await state.update_data(slide_count=count, template_types=[], template_index=0)
    await state.set_state(PresentationForm.template_type)
    available = list_presentation_types()
    if not available:
        await state.clear()
        await message.answer(
            t(lang, "no_templates"),
            reply_markup=build_main_menu(lang=lang, is_admin=_is_admin(message)),
        )
        return
    await message.answer(t(lang, "choose_template", index=1, available=", ".join(str(x) for x in available)))


@router.message(PresentationForm.template_type)
async def process_template_type(message: Message, state: FSMContext) -> None:
    lang, _ = await _lang_and_tokens(message)
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(t(lang, "template_number"))
        return

    selected = int(text)
    available = set(list_presentation_types())
    if selected not in available:
        await message.answer(t(lang, "template_missing", value=selected, available=", ".join(map(str, sorted(available)))))
        return

    data = await state.get_data()
    slide_count = int(data["slide_count"])
    template_types = list(data.get("template_types", []))
    template_types.append(selected)
    template_index = len(template_types)
    await state.update_data(template_types=template_types, template_index=template_index)

    if template_index < slide_count:
        await message.answer(t(lang, "choose_template", index=template_index + 1, available=", ".join(map(str, sorted(available)))))
        return

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

    data = await state.get_data()
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
        )
        file_path = await build_presentation_file(
            topic=topic,
            template_types=template_types,
            slides=slides,
            font_name=font_name,
            font_color=font_color,
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
