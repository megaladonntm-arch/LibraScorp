from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards.main_menu import main_menu_kb
from bot.services.texts import ABOUT_TEXT, HELP_TEXT, WELCOME_TEXT

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb)


@router.message(Command("help"))
@router.message(F.text.casefold() == "помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(F.text.casefold() == "о боте")
async def about_bot(message: Message) -> None:
    await message.answer(ABOUT_TEXT)

