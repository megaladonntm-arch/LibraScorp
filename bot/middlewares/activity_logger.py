from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import load_settings
from bot.db import get_user_ban, get_user_data, log_user_event, upsert_user_profile
from bot.i18n import t

settings = load_settings()


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


def _safe_model_dump_json(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(value.model_dump_json(exclude_none=False))  # type: ignore[attr-defined]
    except Exception:
        return ""


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
            raw_user_json = _safe_model_dump_json(event.from_user)
            raw_chat_json = _safe_model_dump_json(event.chat)

            await upsert_user_profile(
                user_id=event.from_user.id,
                chat_id=event.chat.id if event.chat is not None else 0,
                username=event.from_user.username or "",
                first_name=event.from_user.first_name or "",
                last_name=event.from_user.last_name or "",
                full_name=event.from_user.full_name or "",
                language_code=event.from_user.language_code or "",
                is_bot=bool(event.from_user.is_bot),
                is_premium=event.from_user.is_premium,
                added_to_attachment_menu=event.from_user.added_to_attachment_menu,
                can_join_groups=event.from_user.can_join_groups,
                can_read_all_group_messages=event.from_user.can_read_all_group_messages,
                supports_inline_queries=event.from_user.supports_inline_queries,
                can_connect_to_business=event.from_user.can_connect_to_business,
                has_main_web_app=event.from_user.has_main_web_app,
                last_message_type=message_type,
                last_message_text=payload,
                state_name=state_name,
                raw_user_json=raw_user_json,
                raw_chat_json=raw_chat_json,
            )

            await log_user_event(
                user_id=event.from_user.id,
                username=event.from_user.username or "",
                full_name=event.from_user.full_name or "",
                message_type=message_type,
                message_text=payload,
                state_name=state_name,
            )
            if event.from_user.id != settings.admin_id:
                ban = await get_user_ban(event.from_user.id)
                if ban is not None:
                    reason = ban.reason or "No reason"
                    _, lang = await get_user_data(event.from_user.id, settings.default_tokens)
                    await event.answer(t(lang, "banned_notice", reason=reason))
                    return None
        return await handler(event, data)
