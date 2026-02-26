import asyncio
import logging
import os
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


async def _start_healthcheck_server() -> asyncio.base_events.Server | None:
    port_raw = os.getenv("PORT", "").strip()
    if not port_raw:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        logging.getLogger(__name__).warning("Invalid PORT value: %s", port_raw)
        return None

    async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                await asyncio.wait_for(reader.read(1024), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: 2\r\n"
                b"Connection: close\r\n\r\nOK"
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(_handle_client, host="0.0.0.0", port=port)
    logging.getLogger(__name__).info("Healthcheck server started on 0.0.0.0:%s", port)
    return server


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
    health_server = await _start_healthcheck_server()

    try:
        await dp.start_polling(bot)
    finally:
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
