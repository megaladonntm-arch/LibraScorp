from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.i18n import color_buttons, label


def build_main_menu(lang: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=label(lang, "create_presentation"))],
        [KeyboardButton(text=label(lang, "my_presentations"))],
        [KeyboardButton(text=label(lang, "premium_section"))],
        [KeyboardButton(text=label(lang, "create_template_from_scratch"))],
        [KeyboardButton(text=label(lang, "about")), KeyboardButton(text=label(lang, "help"))],
        [KeyboardButton(text=label(lang, "language"))],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text=label(lang, "admin_panel"))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def build_admin_panel_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label(lang, "issue_tokens")), KeyboardButton(text=label(lang, "remove_tokens"))],
            [KeyboardButton(text=label(lang, "check_tokens")), KeyboardButton(text=label(lang, "template_requests"))],
            [KeyboardButton(text=label(lang, "all_users")), KeyboardButton(text=label(lang, "event_logs"))],
            [KeyboardButton(text=label(lang, "premium_add")), KeyboardButton(text=label(lang, "premium_remove"))],
            [KeyboardButton(text=label(lang, "premium_list"))],
            [KeyboardButton(text=label(lang, "to_menu"))],
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


def build_color_menu(lang: str) -> ReplyKeyboardMarkup:
    options = color_buttons(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=options[0]), KeyboardButton(text=options[1])],
            [KeyboardButton(text=options[2]), KeyboardButton(text=options[3])],
            [KeyboardButton(text=options[4]), KeyboardButton(text=options[5])],
            [KeyboardButton(text=options[6]), KeyboardButton(text=options[7])],
        ],
        resize_keyboard=True,
    )


def build_language_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label(lang, "choose_ru")), KeyboardButton(text=label(lang, "choose_en"))],
            [KeyboardButton(text=label(lang, "choose_uz"))],
            [KeyboardButton(text=label(lang, "to_menu"))],
        ],
        resize_keyboard=True,
    )


def build_premium_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label(lang, "premium_voice_chat"))],
            [KeyboardButton(text=label(lang, "to_menu"))],
        ],
        resize_keyboard=True,
    )
