# Mini Telegram Bot (aiogram 3)

Минимальная структура маленького Telegram-бота.

## Структура

```text
.
├── bot
│   ├── handlers
│   │   ├── __init__.py
│   │   └── common.py
│   ├── keyboards
│   │   ├── __init__.py
│   │   └── main_menu.py
│   ├── services
│   │   ├── __init__.py
│   │   └── texts.py
│   ├── __init__.py
│   ├── config.py
│   └── main.py
├── .env.example
├── .gitignore
└── requirements.txt
```

## Быстрый старт

1. Создай и активируй виртуальное окружение:
   - Windows PowerShell:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Установи зависимости:
   ```powershell
   pip install -r requirements.txt
   ```
3. Создай `.env` на основе примера:
   ```powershell
   Copy-Item .env.example .env
   ```
4. Впиши токен бота в `.env`:
   ```env
   BOT_TOKEN=...
   ```
5. Запусти:
   ```powershell
   python -m bot.main
   ```
