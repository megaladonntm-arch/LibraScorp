TEXTS = {
    "ru": {
        "welcome": (
            "Добро пожаловать в бот для создания презентаций.\n\n"
            "Приложение полностью бесплатное для всех.\n\n"
            "Нажмите «Создать презентацию» или введите /presentation, чтобы начать."
        ),
        "help": (
            "Как пользоваться ботом:\n"
            "1. Нажмите «Создать презентацию».\n"
            "2. Укажите количество слайдов (от 1 до 30).\n"
            "3. Выберите готовое комбо шаблонов или создайте свое.\n"
            "4. Выберите шрифт и цвет текста.\n"
            "5. Отправьте тему презентации.\n"
            "6. При желании добавьте источник: текст, ссылку или файл.\n\n"
            "Лимиты и команды:\n"
            "- Сервис полностью бесплатный для всех\n"
            "- Отмена текущего шага: /cancel\n"
            "- Быстрый запуск: /presentation"
        ),
        "about": (
            "Бот создает структурированный текст слайдов с помощью AI и автоматически "
            "собирает готовый .pptx файл по выбранным шаблонам, шрифту и цвету."
        ),
    },
    "en": {
        "welcome": (
            "Welcome to the presentation generator bot.\n\n"
            "The app is completely free for everyone.\n\n"
            "Press \"Create presentation\" or type /presentation to start."
        ),
        "help": (
            "How to use the bot:\n"
            "1. Press \"Create presentation\".\n"
            "2. Enter the number of slides (1 to 30).\n"
            "3. Choose a template combo or create your own.\n"
            "4. Choose font and text color.\n"
            "5. Send your presentation topic.\n"
            "6. Optionally add source material: text, link, or file.\n\n"
            "Limits and commands:\n"
            "- The service is completely free for everyone\n"
            "- Cancel current flow: /cancel\n"
            "- Quick start: /presentation"
        ),
        "about": (
            "The bot creates structured slide content with AI and automatically builds a "
            "ready-to-use .pptx file using your selected templates, font, and text color."
        ),
    },
    "uz": {
        "welcome": (
            "Taqdimot yaratish botiga xush kelibsiz.\n\n"
            "Ilova hamma uchun mutlaqo bepul.\n\n"
            "Boshlash uchun \"Taqdimot yaratish\" tugmasini bosing yoki /presentation buyrug'ini yuboring."
        ),
        "help": (
            "Botdan foydalanish tartibi:\n"
            "1. \"Taqdimot yaratish\" tugmasini bosing.\n"
            "2. Slayd sonini kiriting (1 dan 30 gacha).\n"
            "3. Shablon komboni tanlang yoki o'zingiznikini yarating.\n"
            "4. Shrift va matn rangini tanlang.\n"
            "5. Taqdimot mavzusini yuboring.\n"
            "6. Ixtiyoriy ravishda manba qo'shing: matn, havola yoki fayl.\n\n"
            "Limitlar va buyruqlar:\n"
            "- Xizmat hamma uchun mutlaqo bepul\n"
            "- Joriy jarayonni bekor qilish: /cancel\n"
            "- Tez boshlash: /presentation"
        ),
        "about": (
            "Bot AI yordamida slaydlar uchun tartibli matn yaratadi va tanlangan shablon, "
            "shrift hamda matn rangiga asoslanib tayyor .pptx faylni avtomatik yig'adi."
        ),
    },
}

# Backward-compatible constants.
WELCOME_TEXT = TEXTS["ru"]["welcome"]
HELP_TEXT = TEXTS["ru"]["help"]
ABOUT_TEXT = TEXTS["ru"]["about"]
