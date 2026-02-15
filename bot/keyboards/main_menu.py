from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Создать презентацию")],
        [KeyboardButton(text="О боте"), KeyboardButton(text="Помощь")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def build_admin_panel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Выдать токены"), KeyboardButton(text="Проверить токены")],
            [KeyboardButton(text="В меню")],
        ],
        resize_keyboard=True,
    )


def build_font_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Times New Roman"), KeyboardButton(text="Arial")],
            [KeyboardButton(text="Calibri"), KeyboardButton(text="Verdana")],
            [KeyboardButton(text="Georgia")],
        ],
        resize_keyboard=True,
    )
