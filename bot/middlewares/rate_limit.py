from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.i18n import t


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, window_sec: int, max_messages: int, admin_id: int = 0) -> None:
        self.window_sec = max(1, int(window_sec))
        self.max_messages = max(2, int(max_messages))
        self.admin_id = int(admin_id)
        self._hits: dict[int, deque[float]] = {}
        self._last_notice_at: dict[int, float] = {}

    def _is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        queue = self._hits.setdefault(user_id, deque())
        border = now - self.window_sec
        while queue and queue[0] < border:
            queue.popleft()
        if len(queue) >= self.max_messages:
            return False
        queue.append(now)
        return True

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        user_id = int(user.id)
        if self.admin_id and user_id == self.admin_id:
            return await handler(event, data)

        if self._is_allowed(user_id):
            return await handler(event, data)

        # Do not spam warning every single update while user is throttled.
        now = time.monotonic()
        if now - self._last_notice_at.get(user_id, 0.0) >= 2.0:
            lang = "ru"
            language_code = getattr(user, "language_code", None)
            if isinstance(language_code, str) and language_code:
                lang = language_code[:2].lower()
            text = t(lang, "rate_limit_exceeded", wait=self.window_sec)
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=False)
            self._last_notice_at[user_id] = now
        return None
