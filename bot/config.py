from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_OPENROUTER_MODELS = (
    "openai/gpt-4o-mini",
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-120b:free",
)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    default_tokens: int
    openrouter_api_key: str
    openrouter_models: tuple[str, ...]
    openrouter_request_timeout_sec: int
    openrouter_max_model_attempts: int
    database_url: str


def _parse_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _parse_models() -> tuple[str, ...]:
    raw = os.getenv("OPENROUTER_MODELS", "")
    if not raw.strip():
        return DEFAULT_OPENROUTER_MODELS
    models = tuple(item.strip() for item in raw.split(",") if item.strip())
    return models or DEFAULT_OPENROUTER_MODELS


def _build_database_url() -> str:
    direct_url = os.getenv("DATABASE_URL")
    if direct_url and direct_url.strip():
        return direct_url.strip()

    db_path_value = os.getenv("DB_PATH", "bot.sqlite3").strip()
    db_path = Path(db_path_value)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    return f"sqlite+aiosqlite:///{db_path.resolve().as_posix()}"


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    load_dotenv(ENV_PATH)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("BOT_TOKEN is required in .env")

    return Settings(
        bot_token=bot_token,
        admin_id=_parse_int("ADMIN_ID", 0),
        default_tokens=_parse_int("DEFAULT_TOKENS", 10),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_models=_parse_models(),
        openrouter_request_timeout_sec=max(10, _parse_int("OPENROUTER_TIMEOUT_SEC", 40)),
        openrouter_max_model_attempts=max(1, _parse_int("OPENROUTER_MAX_MODEL_ATTEMPTS", 2)),
        database_url=_build_database_url(),
    )
