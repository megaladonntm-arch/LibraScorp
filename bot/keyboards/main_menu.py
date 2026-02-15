from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="О боте"), KeyboardButton(text="Помощь")],
    ],
    resize_keyboard=True,
)

