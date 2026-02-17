from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import log_user_event


def _extract_message_payload(message: Message) -> tuple[str, str]:
    if message.text:
        return "text", message.text
    if message.caption:
        return "caption", message.caption
    if message.document:
        file_name = message.document.file_name or "unknown"
        return "document", f"[document] {file_name}"
    if message.photo:
        return "photo", "[photo]"
    if message.voice:
        return "voice", "[voice]"
    if message.audio:
        return "audio", "[audio]"
    if message.video:
        return "video", "[video]"
    return "other", "[unsupported]"


class ActivityLoggerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user is not None:
            state_name = ""
            state = data.get("state")
            if isinstance(state, FSMContext):
                state_name = str(await state.get_state() or "")

            message_type, payload = _extract_message_payload(event)
            await log_user_event(
                user_id=event.from_user.id,
                username=event.from_user.username or "",
                full_name=event.from_user.full_name or "",
                message_type=message_type,
                message_text=payload,
                state_name=state_name,
            )
        return await handler(event, data)
