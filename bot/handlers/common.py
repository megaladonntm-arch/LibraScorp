from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message, ReplyKeyboardRemove

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from bot.keyboards.main_menu import main_menu_kb
from bot.services.ai_text_presentation_generator import (
    generate_slide_content,
    list_presentation_types,
)
from bot.services.presentation_builder import build_presentation_file
from bot.services.texts import ABOUT_TEXT, HELP_TEXT, WELCOME_TEXT

router = Router()


class PresentationForm(StatesGroup):
    template_type = State()
    slide_count = State()
    topic = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb)


@router.message(Command("help"))
@router.message(F.text.casefold() == "помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(F.text.casefold() == "о боте")
async def about_bot(message: Message) -> None:
    await message.answer(ABOUT_TEXT)


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cancel_generation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Генерация отменена.", reply_markup=main_menu_kb)


@router.message(Command("presentation"))
@router.message(F.text.casefold() == "создать презентацию")
async def start_presentation_generation(message: Message, state: FSMContext) -> None:
    types = list_presentation_types()
    if not types:
        await message.answer(
            "Не нашел шаблоны в папке assets_pdf. Добавь файлы вида 1.png, 2.png и т.д."
        )
        return

    await state.set_state(PresentationForm.template_type)
    await message.answer(
        "Выбери тип презентации (номер шаблона из assets_pdf):\n"
        + ", ".join(str(x) for x in types)
        + "\n\nДля отмены: /cancel",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(PresentationForm.template_type)
async def process_template_type(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Введите номер шаблона цифрой, например: 1")
        return

    value = int(text)
    available = set(list_presentation_types())
    if value not in available:
        await message.answer(f"Шаблона {value} нет. Доступно: {', '.join(map(str, sorted(available)))}")
        return

    await state.update_data(template_type=value)
    await state.set_state(PresentationForm.slide_count)
    await message.answer("Сколько слайдов нужно? Введите число от 1 до 30.")


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

    await state.update_data(slide_count=count)
    await state.set_state(PresentationForm.topic)
    await message.answer("Теперь отправь тему презентации.")


@router.message(PresentationForm.topic)
async def process_topic(message: Message, state: FSMContext) -> None:
    topic = (message.text or "").strip()
    if len(topic) < 3:
        await message.answer("Тема слишком короткая. Напиши чуть подробнее.")
        return

    data = await state.get_data()
    template_type = int(data["template_type"])
    slide_count = int(data["slide_count"])

    await message.answer("Генерирую текст и собираю презентацию, это может занять до минуты...")
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        await message.answer("OPENROUTER_API_KEY не найден в .env. Будет использован базовый текст без AI.")

    slides = await generate_slide_content(
        topic=topic,
        slide_count=slide_count,
        template_type=template_type,
    )
    file_path = build_presentation_file(
        topic=topic,
        template_type=template_type,
        slides=slides,
    )

    try:
        await message.answer_document(
            document=FSInputFile(file_path),
            caption=(
                f"Готово.\n"
                f"Тип: {template_type}\n"
                f"Слайдов: {slide_count}\n"
                f"Тема: {topic}"
            ),
            reply_markup=main_menu_kb,
        )
    finally:
        shutil.rmtree(file_path.parent, ignore_errors=True)
        await state.clear()
