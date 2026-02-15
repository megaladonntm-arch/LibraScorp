# Railway Deploy Guide

This project is prepared for Railway as a background worker (Telegram long-polling bot).

## Added Files

- `railway.json` - build/deploy config for Railway
- `Procfile` - worker process fallback (`python -m bot.main`)
- `.python-version` - pins Python `3.12`

## Required Railway Setup

1. Create a Railway project and connect this repository.
2. Open your service settings.
3. Create a **Volume** and mount it to `/data`.
4. Set environment variables in Railway service:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id
DEFAULT_TOKENS=10

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODELS=openai/gpt-4o-mini,deepseek/deepseek-chat-v3-0324:free,meta-llama/llama-3.3-70b-instruct:free,openai/gpt-oss-120b:free

DB_PATH=/data/bot.sqlite3
```

Notes:
- `BOT_TOKEN` is required.
- If `OPENROUTER_API_KEY` is empty, fallback slides are used.
- `DB_PATH=/data/bot.sqlite3` is required for persistent SQLite storage on Railway.

## Deploy

### Option A: GitHub Deploy (recommended)

1. Push current branch to GitHub.
2. Railway will auto-build using `railway.json`.
3. Ensure logs show worker started with `python -m bot.main`.

### Option B: Railway CLI

```bash
railway login
railway link
railway up
```

## Runtime Behavior

- Process type: worker
- Start command: `python -m bot.main`
- Restart policy: `ALWAYS`
- Sleep: disabled
- Replicas: `1`

## Validation Checklist

- Build passes (dependencies from `requirements.txt` installed)
- Service logs show polling started (no `BOT_TOKEN is required in .env` error)
- Bot responds in Telegram
- Volume is mounted to `/data`
- DB file exists at `/data/bot.sqlite3`
