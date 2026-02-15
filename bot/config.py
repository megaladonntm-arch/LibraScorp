from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass
class Settings:
    bot_token: str


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("BOT_TOKEN is not set. Put it in .env file.")
    return Settings(bot_token=token)

