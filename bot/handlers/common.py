from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message, ReplyKeyboardRemove

from bot.config import load_settings
from bot.db import add_user_tokens, get_or_create_user_tokens, try_spend_user_token
from bot.keyboards.main_menu import build_admin_panel_menu, build_font_menu, build_main_menu
from bot.services.ai_text_presentation_generator import generate_slide_content, list_presentation_types
from bot.services.presentation_builder import build_presentation_file
from bot.services.texts import ABOUT_TEXT, HELP_TEXT, WELCOME_TEXT

logger = logging.getLogger(__name__)
router = Router()
settings = load_settings()
COLOR_PATTERN = re.compile(r"^#?[0-9a-fA-F]{6}$")


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


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    tokens = get_or_create_user_tokens(message.from_user.id, settings.default_tokens)
    await message.answer(
        f"{WELCOME_TEXT}\n\nВаши токены: {tokens}",
        reply_markup=build_main_menu(is_admin=_is_admin(message)),
    )


@router.message(Command("help"))
@router.message(F.text.casefold() == "помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(F.text.casefold() == "о боте")
async def about_bot(message: Message) -> None:
    await message.answer(ABOUT_TEXT)


@router.message(Command("tokens"))
async def my_tokens(message: Message) -> None:
    if message.from_user is None:
        return
    tokens = get_or_create_user_tokens(message.from_user.id, settings.default_tokens)
    await message.answer(f"У вас {tokens} токенов.")


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cancel_generation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Генерация отменена.", reply_markup=build_main_menu(is_admin=_is_admin(message)))


@router.message(Command("admin"))
@router.message(F.text == "Админ-панель")
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.clear()
    await message.answer("Панель администратора.", reply_markup=build_admin_panel_menu())


@router.message(F.text == "В меню")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню.", reply_markup=build_main_menu(is_admin=_is_admin(message)))


@router.message(F.text == "Выдать токены")
async def admin_issue_tokens_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminForm.target_user_id)
    await message.answer("Введите ID пользователя, которому выдать токены.")


@router.message(AdminForm.target_user_id)
async def admin_issue_tokens_target(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    await state.update_data(target_user_id=int(text))
    await state.set_state(AdminForm.token_amount)
    await message.answer("Введите количество токенов для начисления.")


@router.message(AdminForm.token_amount)
async def admin_issue_tokens_amount(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not re.fullmatch(r"\d+", text):
        await message.answer("Количество должно быть целым положительным числом.")
        return
    amount = int(text)
    if amount <= 0:
        await message.answer("Количество должно быть больше нуля.")
        return
    data = await state.get_data()
    target_user_id = int(data["target_user_id"])
    new_balance = add_user_tokens(target_user_id, amount, settings.default_tokens)
    await state.clear()
    await message.answer(
        f"Пользователю {target_user_id} начислено {amount} токенов. Текущий баланс: {new_balance}.",
        reply_markup=build_admin_panel_menu(),
    )


@router.message(F.text == "Проверить токены")
async def admin_check_tokens_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminForm.check_user_id)
    await message.answer("Введите ID пользователя для проверки баланса.")


@router.message(AdminForm.check_user_id)
async def admin_check_tokens(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    user_id = int(text)
    balance = get_or_create_user_tokens(user_id, settings.default_tokens)
    await state.clear()
    await message.answer(
        f"Пользователь {user_id}: {balance} токенов.",
        reply_markup=build_admin_panel_menu(),
    )


@router.message(Command("presentation"))
@router.message(F.text.casefold() == "создать презентацию")
async def start_presentation_generation(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    tokens = get_or_create_user_tokens(message.from_user.id, settings.default_tokens)
    if tokens <= 0:
        await message.answer(
            "У вас закончились токены. Обратитесь к администратору.",
            reply_markup=build_main_menu(is_admin=_is_admin(message)),
        )
        return

    await state.clear()
    await state.set_state(PresentationForm.slide_count)
    await message.answer(
        f"Сколько слайдов нужно? Введите число от 1 до 30.\nВаши токены: {tokens}",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(PresentationForm.slide_count)
async def process_slide_count(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Введите количество слайдов числом, например: 7")
        return

    count = int(text)
    if count < 1 or count > 30:
        await message.answer("Количество слайдов должно быть от 1 до 30.")
        return

    await state.update_data(slide_count=count, template_types=[], template_index=0)
    await state.set_state(PresentationForm.template_type)
    available = list_presentation_types()
    if not available:
        await state.clear()
        await message.answer(
            "Не нашёл шаблоны в папке assets_pdf. Добавьте файлы 1.png, 2.png и т.д.",
            reply_markup=build_main_menu(is_admin=_is_admin(message)),
        )
        return
    await message.answer(
        "Выберите шаблон для слайда 1. Доступные номера: " + ", ".join(str(x) for x in available)
    )


@router.message(PresentationForm.template_type)
async def process_template_type(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Введите номер шаблона цифрой, например: 1")
        return

    selected = int(text)
    available = set(list_presentation_types())
    if selected not in available:
        await message.answer(f"Шаблона {selected} нет. Доступно: {', '.join(map(str, sorted(available)))}")
        return

    data = await state.get_data()
    slide_count = int(data["slide_count"])
    template_types = list(data.get("template_types", []))
    template_types.append(selected)
    template_index = len(template_types)
    await state.update_data(template_types=template_types, template_index=template_index)

    if template_index < slide_count:
        await message.answer(f"Выберите шаблон для слайда {template_index + 1}.")
        return

    await state.set_state(PresentationForm.font_name)
    await message.answer("Введите название шрифта или выберите кнопкой.", reply_markup=build_font_menu())


@router.message(PresentationForm.font_name)
async def process_font_name(message: Message, state: FSMContext) -> None:
    font_name = (message.text or "").strip()
    if len(font_name) < 2:
        await message.answer("Введите корректное название шрифта.")
        return
    await state.update_data(font_name=font_name)
    await state.set_state(PresentationForm.font_color)
    await message.answer(
        "Введите цвет текста в формате HEX, например #FFFFFF или FFFFFF.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(PresentationForm.font_color)
async def process_font_color(message: Message, state: FSMContext) -> None:
    color = (message.text or "").strip()
    if not COLOR_PATTERN.fullmatch(color):
        await message.answer("Неверный формат цвета. Пример: #00FFAA")
        return
    normalized = color if color.startswith("#") else f"#{color}"
    await state.update_data(font_color=normalized)
    await state.set_state(PresentationForm.topic)
    await message.answer("Теперь отправьте тему презентации.")


@router.message(PresentationForm.topic)
async def process_topic(message: Message, state: FSMContext) -> None:
    topic = (message.text or "").strip()
    if len(topic) < 3:
        await message.answer("Тема слишком короткая. Напишите чуть подробнее.")
        return
    if message.from_user is None:
        await state.clear()
        return

    data = await state.get_data()
    slide_count = int(data["slide_count"])
    template_types = [int(x) for x in data.get("template_types", [])]
    font_name = str(data["font_name"])
    font_color = str(data["font_color"])

    ok, tokens_left = try_spend_user_token(message.from_user.id, settings.default_tokens)
    if not ok:
        await state.clear()
        await message.answer(
            "У вас закончились токены. Обратитесь к администратору.",
            reply_markup=build_main_menu(is_admin=_is_admin(message)),
        )
        return

    await message.answer("Генерирую текст и собираю презентацию, это может занять до минуты...")

    file_path: Path | None = None
    restore_token = True

    try:
        slides = await generate_slide_content(
            topic=topic,
            slide_count=slide_count,
            template_type=template_types[0] if template_types else 1,
        )
        file_path = build_presentation_file(
            topic=topic,
            template_types=template_types,
            slides=slides,
            font_name=font_name,
            font_color=font_color,
        )
        restore_token = False
        await message.answer_document(
            document=FSInputFile(file_path),
            caption=(
                "Готово.\n"
                f"Слайдов: {slide_count}\n"
                f"Шрифт: {font_name}\n"
                f"Цвет: {font_color}\n"
                f"Токенов осталось: {tokens_left}"
            ),
            reply_markup=build_main_menu(is_admin=_is_admin(message)),
        )
    except Exception as e:
        logger.error("Failed to build presentation: %s", e)
        await message.answer(
            f"Ошибка при создании презентации: {str(e)}",
            reply_markup=build_main_menu(is_admin=_is_admin(message)),
        )
    finally:
        if restore_token:
            add_user_tokens(message.from_user.id, 1, settings.default_tokens)
        if file_path is not None:
            shutil.rmtree(file_path.parent, ignore_errors=True)
        await state.clear()
