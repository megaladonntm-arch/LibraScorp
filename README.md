# Telegram AI Presentation Bot (aiogram 3)

Бот собирает презентацию `.pptx`:
1. Пользователь выбирает тип (номер файла из `assets_pdf`).
2. Указывает количество слайдов.
3. Вводит тему.
4. Бот генерирует текст через AI и отправляет готовый файл.

## Структура

```text
.
├── assets_pdf
│   └── 1.png
├── bot
│   ├── handlers
│   │   ├── __init__.py
│   │   └── common.py
│   ├── keyboards
│   │   ├── __init__.py
│   │   └── main_menu.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── ai_text_presentation_generator.py
│   │   ├── presentation_builder.py
│   │   └── texts.py
│   ├── __init__.py
│   ├── config.py
│   └── main.py
├── .env.example
├── .gitignore
└── requirements.txt
```

## Требования к шаблонам

- Папка: `assets_pdf/`
- Имена файлов начинаются с номера шаблона: `1.png`, `2.jpg`, `3.jpeg`
- Сейчас фоном презентации используются изображения (`png/jpg/jpeg`)

## Быстрый старт

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Заполни `.env`:

```env
BOT_TOKEN=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Запуск:

```powershell
python -m bot.main
```

## Команды

- `/start` - главное меню
- `/presentation` - запуск генерации презентации
- `/help` - справка
- `/cancel` - отмена текущего шага
