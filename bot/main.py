import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.config import load_settings
from bot.db import init_db
from bot.handlers import setup_routers
from bot.middlewares import ActivityLoggerMiddleware, RateLimitMiddleware



async def main() -> None:
    settings = load_settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    await init_db()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(
        RateLimitMiddleware(
            window_sec=settings.per_user_rate_limit_window_sec,
            max_messages=settings.per_user_rate_limit_max_messages,
            admin_id=settings.admin_id,
        )
    )
    dp.message.outer_middleware(ActivityLoggerMiddleware())
    dp.include_router(setup_routers())

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
