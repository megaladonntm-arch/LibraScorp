from __future__ import annotations

LANGS = ("ru", "en", "uz")

LABELS = {
    "create_presentation": {"ru": "Создать презентацию", "en": "Create presentation", "uz": "Taqdimot yaratish"},
    "my_presentations": {"ru": "Мои презентации", "en": "My presentations", "uz": "Mening taqdimotlarim"},
    "about": {"ru": "О боте", "en": "About", "uz": "Bot haqida"},
    "help": {"ru": "Помощь", "en": "Help", "uz": "Yordam"},
    "admin_panel": {"ru": "Админ-панель", "en": "Admin panel", "uz": "Admin panel"},
    "issue_tokens": {"ru": "Выдать токены", "en": "Issue tokens", "uz": "Token berish"},
    "check_tokens": {"ru": "Проверить токены", "en": "Check tokens", "uz": "Tokenni tekshirish"},
    "all_users": {"ru": "Все пользователи", "en": "All users", "uz": "Barcha foydalanuvchilar"},
    "event_logs": {"ru": "Логи сообщений", "en": "Message logs", "uz": "Xabar loglari"},
    "to_menu": {"ru": "В меню", "en": "To menu", "uz": "Menyuga"},
    "language": {"ru": "Язык", "en": "Language", "uz": "Til"},
    "choose_ru": {"ru": "Русский", "en": "Russian", "uz": "Rus tili"},
    "choose_en": {"ru": "Английский", "en": "English", "uz": "Ingliz tili"},
    "choose_uz": {"ru": "Узбекский", "en": "Uzbek", "uz": "O'zbek tili"},
}

COLORS = {
    "black": {"hex": "#000000", "ru": "Черный", "en": "Black", "uz": "Qora"},
    "white": {"hex": "#FFFFFF", "ru": "Белый", "en": "White", "uz": "Oq"},
    "red": {"hex": "#FF0000", "ru": "Красный", "en": "Red", "uz": "Qizil"},
    "blue": {"hex": "#0066FF", "ru": "Синий", "en": "Blue", "uz": "Ko'k"},
    "green": {"hex": "#00AA55", "ru": "Зеленый", "en": "Green", "uz": "Yashil"},
    "yellow": {"hex": "#FFD700", "ru": "Желтый", "en": "Yellow", "uz": "Sariq"},
    "orange": {"hex": "#FF8C00", "ru": "Оранжевый", "en": "Orange", "uz": "To'q sariq"},
    "purple": {"hex": "#8A2BE2", "ru": "Фиолетовый", "en": "Purple", "uz": "Binafsha"},
}

TEXTS = {
    "ru": {
        "welcome": "Привет. Это бот для генерации презентаций.",
        "help": "Как пользоваться:\n1. Нажми «Создать презентацию».\n2. Укажи количество слайдов.\n3. Выбери готовое комбо шаблонов или создай свое.\n4. Выбери шрифт и цвет текста.\n5. Напиши тему и источник (по желанию).\n\n1 презентация = 1 токен.",
        "about": "Бот генерирует текст слайдов через AI и собирает .pptx файл.",
        "tokens_info": "Ваши токены: {tokens}",
        "generation_cancelled": "Генерация отменена.",
        "access_denied": "Доступ запрещен.",
        "admin_panel": "Панель администратора.",
        "main_menu": "Главное меню.",
        "ask_target_user_id": "Введите ID пользователя, которому выдать токены.",
        "id_must_number": "ID должен быть числом.",
        "ask_token_amount": "Введите количество токенов для начисления.",
        "amount_must_int": "Количество должно быть целым положительным числом.",
        "amount_gt_zero": "Количество должно быть больше нуля.",
        "tokens_added": "Пользователю {user_id} начислено {amount} токенов. Текущий баланс: {balance}.",
        "ask_check_user_id": "Введите ID пользователя для проверки баланса.",
        "user_tokens": "Пользователь {user_id}: {tokens} токенов.",
        "all_users_title": "Пользователи ({count}):",
        "all_users_empty": "Пользователи пока отсутствуют.",
        "event_logs_title": "Последние сообщения ({count}):",
        "event_logs_empty": "Логи пока пусты.",
        "no_tokens": "У вас закончились токены. Обратитесь к администратору.",
        "ask_slide_count": "Сколько слайдов нужно? Введите число от 1 до 30.\nВаши токены: {tokens}",
        "slide_count_number": "Введите количество слайдов числом, например: 7",
        "slide_count_range": "Количество слайдов должно быть от 1 до 30.",
        "no_templates": "Не нашёл шаблоны в папке assets_pdf. Добавьте файлы 1.png, 2.png и т.д.",
        "choose_template": "Выберите шаблон.",
        "choose_combo_title": "Выберите комбо шаблонов:",
        "choose_combo_hint": "Отправьте номер комбо.\nЧтобы сохранить свое: new Название: 1,2,3\nДоступные шаблоны: {available}",
        "combo_pick_number": "Отправьте номер из списка комбо.",
        "combo_new_format": "Формат сохранения: new Название: 1,2,3",
        "combo_name_short": "Название комбо слишком короткое.",
        "combo_invalid_sequence": "Некорректная последовательность. Используйте только доступные номера через запятую.",
        "combo_saved": "Комбо «{name}» сохранено и выбрано.",
        "template_number": "Введите номер шаблона цифрой, например: 1",
        "template_missing": "Шаблона {value} нет. Доступно: {available}",
        "ask_font": "Введите название шрифта или выберите кнопкой.",
        "invalid_font": "Введите корректное название шрифта.",
        "ask_color": "Выберите готовый цвет текста кнопкой.",
        "invalid_color": "Выберите цвет из кнопок.",
        "ask_template_color": "🎨 Выбери цвет для шаблона (1-5):",
        "template_color_blue": "Blue",
        "template_color_purple": "Purple",
        "template_color_red": "Red",
        "template_color_orange": "Orange",
        "template_color_green": "Green",
        "ask_topic": "Теперь отправьте тему презентации.",
        "ask_source_material": "Отправьте источник для презентации: текст, ссылку или .txt/.md/.csv/.json/.log файл.\nЕсли источник не нужен, отправьте: skip",
        "source_invalid_input": "Отправьте текст, ссылку или поддерживаемый файл.",
        "source_file_too_large": "Файл слишком большой. Максимум 2 МБ.",
        "source_file_type_unsupported": "Неподдерживаемый тип файла. Разрешено: {exts}",
        "source_url_fetch_error": "Не удалось получить текст по ссылке. Проверьте URL или отправьте текст/файл.",
        "topic_short": "Тема слишком короткая. Напишите чуть подробнее.",
        "generating": "Генерирую текст и собираю презентацию, это может занять до минуты...",
        "ready": "Готово.\nСлайдов: {slides}\nШрифт: {font}\nЦвет: {color}\nТокенов осталось: {tokens}",
        "build_error": "Ошибка при создании презентации: {error}",
        "my_tokens": "У вас {tokens} токенов.",
        "my_presentations_empty": "У вас пока нет сохраненных презентаций.",
        "my_presentations_title": "Последние презентации:",
        "my_combos_empty": "У вас пока нет сохраненных комбо.",
        "my_combos_title": "Ваши комбо шаблонов:",
        "choose_language": "Выберите язык.",
        "language_changed": "Язык изменен.",
    },
    "en": {
        "welcome": "Hi. This bot generates presentations.",
        "help": "How to use:\n1. Press Create presentation.\n2. Enter slide count.\n3. Pick a template combo or create your own.\n4. Choose font and text color.\n5. Enter topic and optional source.\n\n1 presentation = 1 token.",
        "about": "The bot generates slide text with AI and builds a .pptx file.",
        "tokens_info": "Your tokens: {tokens}",
        "generation_cancelled": "Generation canceled.",
        "access_denied": "Access denied.",
        "admin_panel": "Admin panel.",
        "main_menu": "Main menu.",
        "ask_target_user_id": "Enter user ID to issue tokens.",
        "id_must_number": "ID must be a number.",
        "ask_token_amount": "Enter token amount to add.",
        "amount_must_int": "Amount must be a positive integer.",
        "amount_gt_zero": "Amount must be greater than zero.",
        "tokens_added": "Added {amount} tokens to user {user_id}. Current balance: {balance}.",
        "ask_check_user_id": "Enter user ID to check balance.",
        "user_tokens": "User {user_id}: {tokens} tokens.",
        "all_users_title": "Users ({count}):",
        "all_users_empty": "No users yet.",
        "event_logs_title": "Recent messages ({count}):",
        "event_logs_empty": "No logs yet.",
        "no_tokens": "You have no tokens left. Contact admin.",
        "ask_slide_count": "How many slides do you need? Enter 1 to 30.\nYour tokens: {tokens}",
        "slide_count_number": "Enter slide count as a number, for example: 7",
        "slide_count_range": "Slide count must be from 1 to 30.",
        "no_templates": "No templates found in assets_pdf. Add files like 1.png, 2.png.",
        "choose_template": "Choose template.",
        "choose_combo_title": "Choose a template combo:",
        "choose_combo_hint": "Send combo number.\nTo save your own: new Name: 1,2,3\nAvailable templates: {available}",
        "combo_pick_number": "Send a combo number from the list.",
        "combo_new_format": "Save format: new Name: 1,2,3",
        "combo_name_short": "Combo name is too short.",
        "combo_invalid_sequence": "Invalid sequence. Use only available template numbers separated by commas.",
        "combo_saved": "Combo \"{name}\" saved and selected.",
        "template_number": "Enter template number, for example: 1",
        "template_missing": "Template {value} not found. Available: {available}",
        "ask_font": "Enter font name or choose a button.",
        "invalid_font": "Enter a valid font name.",
        "ask_color": "Choose a ready text color using buttons.",
        "invalid_color": "Choose a color from buttons.",
        "ask_template_color": "🎨 Choose template color (1-5):",
        "template_color_blue": "Blue",
        "template_color_purple": "Purple",
        "template_color_red": "Red",
        "template_color_orange": "Orange",
        "template_color_green": "Green",
        "ask_topic": "Now send presentation topic.",
        "ask_source_material": "Send source material: text, link, or a .txt/.md/.csv/.json/.log file.\nIf you want to skip, send: skip",
        "source_invalid_input": "Send text, link, or a supported file.",
        "source_file_too_large": "The file is too large. Maximum size is 2 MB.",
        "source_file_type_unsupported": "Unsupported file type. Allowed: {exts}",
        "source_url_fetch_error": "Could not fetch text from the link. Check URL or send text/file instead.",
        "topic_short": "Topic is too short. Please provide more details.",
        "generating": "Generating text and building presentation, this may take up to a minute...",
        "ready": "Done.\nSlides: {slides}\nFont: {font}\nColor: {color}\nTokens left: {tokens}",
        "build_error": "Failed to create presentation: {error}",
        "my_tokens": "You have {tokens} tokens.",
        "my_presentations_empty": "You do not have saved presentations yet.",
        "my_presentations_title": "Your recent presentations:",
        "my_combos_empty": "You have no saved combos yet.",
        "my_combos_title": "Your template combos:",
        "choose_language": "Choose language.",
        "language_changed": "Language updated.",
    },
    "uz": {
        "welcome": "Salom. Bu bot taqdimot yaratadi.",
        "help": "Foydalanish:\n1. Taqdimot yaratish tugmasini bosing.\n2. Slayd sonini kiriting.\n3. Shablon kombosini tanlang yoki o'zingiznikini yarating.\n4. Shrift va matn rangini tanlang.\n5. Mavzu va ixtiyoriy manbani yuboring.\n\n1 taqdimot = 1 token.",
        "about": "Bot AI yordamida slayd matnini yaratadi va .pptx fayl yig'adi.",
        "tokens_info": "Tokenlaringiz: {tokens}",
        "generation_cancelled": "Yaratish bekor qilindi.",
        "access_denied": "Ruxsat yo'q.",
        "admin_panel": "Admin panel.",
        "main_menu": "Asosiy menyu.",
        "ask_target_user_id": "Token berish uchun foydalanuvchi ID sini kiriting.",
        "id_must_number": "ID raqam bo'lishi kerak.",
        "ask_token_amount": "Qo'shiladigan token sonini kiriting.",
        "amount_must_int": "Soni musbat butun son bo'lishi kerak.",
        "amount_gt_zero": "Soni noldan katta bo'lishi kerak.",
        "tokens_added": "{user_id} foydalanuvchiga {amount} token qo'shildi. Joriy balans: {balance}.",
        "ask_check_user_id": "Balansni tekshirish uchun foydalanuvchi ID sini kiriting.",
        "user_tokens": "Foydalanuvchi {user_id}: {tokens} token.",
        "all_users_title": "Foydalanuvchilar ({count}):",
        "all_users_empty": "Hozircha foydalanuvchilar yo'q.",
        "event_logs_title": "Oxirgi xabarlar ({count}):",
        "event_logs_empty": "Loglar hozircha bo'sh.",
        "no_tokens": "Token tugagan. Adminga murojaat qiling.",
        "ask_slide_count": "Nechta slayd kerak? 1 dan 30 gacha kiriting.\nTokenlaringiz: {tokens}",
        "slide_count_number": "Slayd sonini raqam bilan kiriting, masalan: 7",
        "slide_count_range": "Slayd soni 1 dan 30 gacha bo'lishi kerak.",
        "no_templates": "assets_pdf papkasida shablon topilmadi. 1.png, 2.png kabi fayllar qo'shing.",
        "choose_template": "Shablonni tanlang.",
        "choose_combo_title": "Shablon kombo tanlang:",
        "choose_combo_hint": "Kombo raqamini yuboring.\nSaqlash uchun: new Nomi: 1,2,3\nMavjud shablonlar: {available}",
        "combo_pick_number": "Ro'yxatdan kombo raqamini yuboring.",
        "combo_new_format": "Saqlash formati: new Nomi: 1,2,3",
        "combo_name_short": "Kombo nomi juda qisqa.",
        "combo_invalid_sequence": "Noto'g'ri ketma-ketlik. Faqat mavjud shablon raqamlarini vergul bilan yuboring.",
        "combo_saved": "\"{name}\" kombo saqlandi va tanlandi.",
        "template_number": "Shablon raqamini kiriting, masalan: 1",
        "template_missing": "{value} shablon topilmadi. Mavjud: {available}",
        "ask_font": "Shrift nomini kiriting yoki tugmadan tanlang.",
        "invalid_font": "To'g'ri shrift nomini kiriting.",
        "ask_color": "Matn uchun tayyor rangni tugmadan tanlang.",
        "invalid_color": "Rangni tugmalardan tanlang.",
        "ask_template_color": "🎨 Shablon uchun rangni tanlang (1-5):",
        "template_color_blue": "Ko'k",
        "template_color_purple": "Binafsha",
        "template_color_red": "Qizil",
        "template_color_orange": "To'q sariq",
        "template_color_green": "Yashil",
        "ask_topic": "Endi taqdimot mavzusini yuboring.",
        "ask_source_material": "Taqdimot uchun manba yuboring: matn, havola yoki .txt/.md/.csv/.json/.log fayl.\nO'tkazib yuborish uchun: skip",
        "source_invalid_input": "Matn, havola yoki qo'llab-quvvatlanadigan fayl yuboring.",
        "source_file_too_large": "Fayl juda katta. Maksimal hajm 2 MB.",
        "source_file_type_unsupported": "Qo'llab-quvvatlanmaydigan fayl turi. Ruxsat etilgan: {exts}",
        "source_url_fetch_error": "Havoladan matn olinmadi. URL ni tekshiring yoki matn/fayl yuboring.",
        "topic_short": "Mavzu juda qisqa. Batafsilroq yozing.",
        "generating": "Matn yaratilmoqda va taqdimot yig'ilmoqda, bu bir daqiqagacha davom etishi mumkin...",
        "ready": "Tayyor.\nSlaydlar: {slides}\nShrift: {font}\nRang: {color}\nQolgan token: {tokens}",
        "build_error": "Taqdimot yaratishda xatolik: {error}",
        "my_tokens": "Sizda {tokens} token bor.",
        "my_presentations_empty": "Sizda hozircha saqlangan taqdimotlar yo'q.",
        "my_presentations_title": "Oxirgi taqdimotlaringiz:",
        "my_combos_empty": "Sizda hozircha saqlangan kombo yo'q.",
        "my_combos_title": "Sizning shablon kombolaringiz:",
        "choose_language": "Tilni tanlang.",
        "language_changed": "Til o'zgartirildi.",
    },
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGS else "ru"


def t(lang: str, key: str, **kwargs: object) -> str:
    effective_lang = normalize_lang(lang)
    template = TEXTS[effective_lang][key]
    return template.format(**kwargs)


def label(lang: str, key: str) -> str:
    effective_lang = normalize_lang(lang)
    return LABELS[key][effective_lang]


def is_action_text(value: str | None, key: str) -> bool:
    if not value:
        return False
    normalized = value.strip().casefold()
    return normalized in {labels.casefold() for labels in LABELS[key].values()}


def detect_language(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold()
    mapping = {
        LABELS["choose_ru"]["ru"].casefold(): "ru",
        LABELS["choose_ru"]["en"].casefold(): "ru",
        LABELS["choose_ru"]["uz"].casefold(): "ru",
        "ru": "ru",
        "рус": "ru",
        LABELS["choose_en"]["ru"].casefold(): "en",
        LABELS["choose_en"]["en"].casefold(): "en",
        LABELS["choose_en"]["uz"].casefold(): "en",
        "en": "en",
        LABELS["choose_uz"]["ru"].casefold(): "uz",
        LABELS["choose_uz"]["en"].casefold(): "uz",
        LABELS["choose_uz"]["uz"].casefold(): "uz",
        "uz": "uz",
    }
    return mapping.get(normalized)


def color_buttons(lang: str) -> list[str]:
    effective_lang = normalize_lang(lang)
    return [COLORS[key][effective_lang] for key in COLORS]


def color_hex_by_text(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    normalized = value.strip().casefold()
    for color in COLORS.values():
        for lang in LANGS:
            if normalized == str(color[lang]).casefold():
                return str(color["hex"]), str(color[lang])
    return None
