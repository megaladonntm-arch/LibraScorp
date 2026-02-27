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
    log_level: str
    per_user_rate_limit_window_sec: int
    per_user_rate_limit_max_messages: int
    openrouter_api_key: str
    openrouter_models: tuple[str, ...]
    openrouter_request_timeout_sec: int
    openrouter_max_model_attempts: int
    database_url: str
    auto_topic_images_enabled: bool
    auto_topic_images_max_count: int
    pexels_api_key: str
    pexels_request_timeout_sec: int


def _parse_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _parse_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_models() -> tuple[str, ...]:
    raw = os.getenv("OPENROUTER_MODELS", "")
    if not raw.strip():
        return DEFAULT_OPENROUTER_MODELS
    models = tuple(item.strip() for item in raw.split(",") if item.strip())
    return models or DEFAULT_OPENROUTER_MODELS


def _build_database_url() -> str:
    direct_url = os.getenv("DATABASE_URL")
    if direct_url and direct_url.strip():
        normalized_url = direct_url.strip()
        # Railway/Postgres providers often expose sync URLs like:
        # postgres://... or postgresql://...
        # This app uses SQLAlchemy async engine, so force asyncpg driver.
        if normalized_url.startswith("postgres://"):
            return "postgresql+asyncpg://" + normalized_url[len("postgres://") :]
        if normalized_url.startswith("postgresql://") and "+asyncpg" not in normalized_url:
            return "postgresql+asyncpg://" + normalized_url[len("postgresql://") :]
        return normalized_url

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
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        per_user_rate_limit_window_sec=max(1, _parse_int("RATE_LIMIT_WINDOW_SEC", 8)),
        per_user_rate_limit_max_messages=max(2, _parse_int("RATE_LIMIT_MAX_MESSAGES", 12)),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_models=_parse_models(),
        openrouter_request_timeout_sec=max(10, _parse_int("OPENROUTER_TIMEOUT_SEC", 40)),
        openrouter_max_model_attempts=max(1, _parse_int("OPENROUTER_MAX_MODEL_ATTEMPTS", 2)),
        database_url=_build_database_url(),
        auto_topic_images_enabled=_parse_bool("AUTO_TOPIC_IMAGES_ENABLED", True),
        auto_topic_images_max_count=max(1, _parse_int("AUTO_TOPIC_IMAGES_MAX_COUNT", 20)),
        pexels_api_key=os.getenv("PEXELS_API_KEY", "").strip(),
        pexels_request_timeout_sec=max(5, _parse_int("PEXELS_TIMEOUT_SEC", 15)),
    )
