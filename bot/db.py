from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot.config import load_settings

settings = load_settings()


class Base(DeclarativeBase):
    pass


class UserBalance(Base):
    __tablename__ = "user_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="ru")


class PresentationHistory(Base):
    __tablename__ = "presentation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False)
    template_types: Mapped[str] = mapped_column(String(500), nullable=False)
    font_name: Mapped[str] = mapped_column(String(100), nullable=False)
    font_color: Mapped[str] = mapped_column(String(7), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserEventLog(Base):
    __tablename__ = "user_event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    message_text: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    state_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False, default=0)
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    language_code: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_premium: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    added_to_attachment_menu: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_join_groups: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_read_all_group_messages: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    supports_inline_queries: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_connect_to_business: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_main_web_app: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    last_message_text: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    last_state_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    raw_user_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_chat_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserBan(Base):
    __tablename__ = "user_bans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    banned_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserTemplateCombo(Base):
    __tablename__ = "user_template_combos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    templates_csv: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GlobalTemplateCombo(Base):
    __tablename__ = "global_template_combos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    templates_csv: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TemplateSubmissionLog(Base):
    __tablename__ = "template_submission_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    combo_name: Mapped[str] = mapped_column(String(80), nullable=False)
    templates_csv: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PremiumUser(Base):
    __tablename__ = "premium_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


engine = create_async_engine(settings.database_url, future=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, future=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Backward-compatible migration for old SQLite databases.
        if conn.dialect.name == "sqlite":
            columns = (await conn.execute(text("PRAGMA table_info(user_balances)"))).fetchall()
            names = {str(col[1]) for col in columns}
            if "language" not in names:
                await conn.execute(text("ALTER TABLE user_balances ADD COLUMN language VARCHAR(2) NOT NULL DEFAULT 'ru'"))


async def _get_or_create_user(session: AsyncSession, user_id: int, default_tokens: int) -> UserBalance:
    result = await session.execute(
        select(UserBalance).where(UserBalance.telegram_user_id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = UserBalance(telegram_user_id=user_id, tokens=default_tokens, language="ru")
        session.add(user)
        await session.flush()
    return user


async def get_user_data(user_id: int, default_tokens: int = 10) -> tuple[int, str]:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        await session.commit()
        return user.tokens, user.language


async def get_or_create_user_tokens(user_id: int, default_tokens: int = 10) -> int:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        await session.commit()
        return user.tokens


async def get_user_language(user_id: int, default_tokens: int = 10) -> str:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        await session.commit()
        return user.language


async def set_user_language(user_id: int, language: str, default_tokens: int = 10) -> str:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        user.language = language
        await session.flush()
        await session.commit()
        return user.language


async def try_spend_user_token(user_id: int, default_tokens: int = 10) -> tuple[bool, int]:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        if user.tokens <= 0:
            await session.commit()
            return False, user.tokens
        user.tokens -= 1
        await session.flush()
        await session.commit()
        return True, user.tokens


async def add_user_tokens(user_id: int, amount: int, default_tokens: int = 10) -> int:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        user.tokens += amount
        await session.flush()
        await session.commit()
        return user.tokens


async def remove_user_tokens(user_id: int, amount: int, default_tokens: int = 10) -> int:
    async with SessionLocal() as session:
        user = await _get_or_create_user(session, user_id, default_tokens)
        user.tokens = max(0, user.tokens - max(0, amount))
        await session.flush()
        await session.commit()
        return user.tokens


async def add_presentation_history(
    user_id: int,
    topic: str,
    slide_count: int,
    template_types: list[int],
    font_name: str,
    font_color: str,
    language: str,
) -> None:
    
    async with SessionLocal() as session:
        record = PresentationHistory(
            telegram_user_id=user_id,
            topic=topic[:300],
            slide_count=slide_count,
            template_types=",".join(str(item) for item in template_types)[:500],
            font_name=font_name[:100],
            font_color=font_color[:7],
            language=language[:2],
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        await session.commit()


async def get_user_presentation_history(
    user_id: int,
    limit: int = 10,
) -> list[PresentationHistory]:
    effective_limit = max(1, min(limit, 50))
    async with SessionLocal() as session:
        result = await session.execute(
            select(PresentationHistory)
            .where(PresentationHistory.telegram_user_id == user_id)
            .order_by(PresentationHistory.created_at.desc(), PresentationHistory.id.desc())
            .limit(effective_limit)
        )
        return list(result.scalars().all())


async def log_user_event(
    user_id: int,
    username: str,
    full_name: str,
    message_type: str,
    message_text: str,
    state_name: str,
) -> None:
    async with SessionLocal() as session:
        row = UserEventLog(
            telegram_user_id=user_id,
            username=username[:64],
            full_name=full_name[:255],
            message_type=message_type[:32],
            message_text=message_text[:1000],
            state_name=state_name[:255],
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.flush()
        await session.commit()


async def upsert_user_profile(
    user_id: int,
    chat_id: int,
    username: str,
    first_name: str,
    last_name: str,
    full_name: str,
    language_code: str,
    is_bot: bool,
    is_premium: bool | None,
    added_to_attachment_menu: bool | None,
    can_join_groups: bool | None,
    can_read_all_group_messages: bool | None,
    supports_inline_queries: bool | None,
    can_connect_to_business: bool | None,
    has_main_web_app: bool | None,
    last_message_type: str,
    last_message_text: str,
    state_name: str,
    raw_user_json: str,
    raw_chat_json: str,
) -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.telegram_user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = UserProfile(
                telegram_user_id=user_id,
                chat_id=chat_id,
                username=username[:64],
                first_name=first_name[:128],
                last_name=last_name[:128],
                full_name=full_name[:255],
                language_code=language_code[:12],
                is_bot=is_bot,
                is_premium=is_premium,
                added_to_attachment_menu=added_to_attachment_menu,
                can_join_groups=can_join_groups,
                can_read_all_group_messages=can_read_all_group_messages,
                supports_inline_queries=supports_inline_queries,
                can_connect_to_business=can_connect_to_business,
                has_main_web_app=has_main_web_app,
                last_message_type=last_message_type[:32],
                last_message_text=last_message_text[:1000],
                last_state_name=state_name[:255],
                raw_user_json=raw_user_json[:10000],
                raw_chat_json=raw_chat_json[:10000],
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(row)
        else:
            row.chat_id = chat_id
            row.username = username[:64]
            row.first_name = first_name[:128]
            row.last_name = last_name[:128]
            row.full_name = full_name[:255]
            row.language_code = language_code[:12]
            row.is_bot = is_bot
            row.is_premium = is_premium
            row.added_to_attachment_menu = added_to_attachment_menu
            row.can_join_groups = can_join_groups
            row.can_read_all_group_messages = can_read_all_group_messages
            row.supports_inline_queries = supports_inline_queries
            row.can_connect_to_business = can_connect_to_business
            row.has_main_web_app = has_main_web_app
            row.last_message_type = last_message_type[:32]
            row.last_message_text = last_message_text[:1000]
            row.last_state_name = state_name[:255]
            row.raw_user_json = raw_user_json[:10000]
            row.raw_chat_json = raw_chat_json[:10000]
            row.last_seen_at = now
        await session.flush()
        await session.commit()


async def get_recent_user_events(limit: int = 100) -> list[UserEventLog]:
    effective_limit = max(1, min(limit, 500))
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserEventLog)
            .order_by(UserEventLog.created_at.desc(), UserEventLog.id.desc())
            .limit(effective_limit)
        )
        return list(result.scalars().all())


async def get_all_users() -> list[UserBalance]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserBalance).order_by(UserBalance.id.asc())
        )
        return list(result.scalars().all())


async def get_all_user_profiles(limit: int = 1000) -> list[UserProfile]:
    effective_limit = max(1, min(limit, 10000))
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserProfile)
            .order_by(UserProfile.last_seen_at.desc(), UserProfile.id.desc())
            .limit(effective_limit)
        )
        return list(result.scalars().all())


async def get_user_profile(user_id: int) -> UserProfile | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.telegram_user_id == user_id)
        )
        return result.scalar_one_or_none()


async def get_broadcast_user_ids(limit: int = 10000) -> list[int]:
    effective_limit = max(1, min(limit, 50000))
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserProfile.telegram_user_id)
            .order_by(UserProfile.last_seen_at.desc(), UserProfile.id.desc())
            .limit(effective_limit)
        )
        ids = [int(row[0]) for row in result.all()]
        if ids:
            return ids
        fallback = await session.execute(
            select(UserBalance.telegram_user_id).order_by(UserBalance.id.asc()).limit(effective_limit)
        )
        return [int(row[0]) for row in fallback.all()]


async def set_user_ban(user_id: int, reason: str, banned_by_user_id: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserBan).where(UserBan.telegram_user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.reason = reason[:500]
            row.banned_by_user_id = banned_by_user_id
            row.created_at = datetime.now(timezone.utc)
            await session.flush()
            await session.commit()
            return False
        row = UserBan(
            telegram_user_id=user_id,
            reason=reason[:500],
            banned_by_user_id=banned_by_user_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.flush()
        await session.commit()
        return True


async def remove_user_ban(user_id: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserBan).where(UserBan.telegram_user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        await session.commit()
        return True


async def get_user_ban(user_id: int) -> UserBan | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserBan).where(UserBan.telegram_user_id == user_id)
        )
        return result.scalar_one_or_none()


async def is_user_banned(user_id: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserBan.id).where(UserBan.telegram_user_id == user_id)
        )
        return result.scalar_one_or_none() is not None


async def get_user_template_combos(user_id: int) -> list[UserTemplateCombo]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTemplateCombo)
            .where(UserTemplateCombo.telegram_user_id == user_id)
            .order_by(UserTemplateCombo.updated_at.desc(), UserTemplateCombo.id.desc())
        )
        return list(result.scalars().all())


async def upsert_user_template_combo(user_id: int, name: str, template_types: list[int]) -> None:
    now = datetime.now(timezone.utc)
    normalized_name = name.strip()[:80]
    csv_value = ",".join(str(item) for item in template_types)[:500]
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserTemplateCombo).where(
                UserTemplateCombo.telegram_user_id == user_id,
                UserTemplateCombo.name == normalized_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = UserTemplateCombo(
                telegram_user_id=user_id,
                name=normalized_name,
                templates_csv=csv_value,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.templates_csv = csv_value
            row.updated_at = now
        await session.flush()
        await session.commit()


async def get_global_template_combos() -> list[GlobalTemplateCombo]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(GlobalTemplateCombo).order_by(GlobalTemplateCombo.updated_at.desc(), GlobalTemplateCombo.id.desc())
        )
        return list(result.scalars().all())


async def upsert_global_template_combo(name: str, template_types: list[int], created_by_user_id: int) -> None:
    now = datetime.now(timezone.utc)
    normalized_name = name.strip()[:80]
    csv_value = ",".join(str(item) for item in template_types)[:500]
    async with SessionLocal() as session:
        result = await session.execute(
            select(GlobalTemplateCombo).where(GlobalTemplateCombo.name == normalized_name)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = GlobalTemplateCombo(
                name=normalized_name,
                templates_csv=csv_value,
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.templates_csv = csv_value
            row.created_by_user_id = created_by_user_id
            row.updated_at = now
        await session.flush()
        await session.commit()


async def add_template_submission_log(user_id: int, combo_name: str, template_types: list[int]) -> None:
    now = datetime.now(timezone.utc)
    csv_value = ",".join(str(item) for item in template_types)[:500]
    async with SessionLocal() as session:
        row = TemplateSubmissionLog(
            telegram_user_id=user_id,
            combo_name=combo_name.strip()[:80],
            templates_csv=csv_value,
            created_at=now,
        )
        session.add(row)
        await session.flush()
        await session.commit()


async def get_recent_template_submissions(limit: int = 100) -> list[TemplateSubmissionLog]:
    effective_limit = max(1, min(limit, 300))
    async with SessionLocal() as session:
        result = await session.execute(
            select(TemplateSubmissionLog)
            .order_by(TemplateSubmissionLog.created_at.desc(), TemplateSubmissionLog.id.desc())
            .limit(effective_limit)
        )
        return list(result.scalars().all())


async def set_premium_user(user_id: int, assigned_by_user_id: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(PremiumUser).where(PremiumUser.telegram_user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return False
        row = PremiumUser(
            telegram_user_id=user_id,
            assigned_by_user_id=assigned_by_user_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.flush()
        await session.commit()
        return True


async def remove_premium_user(user_id: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(PremiumUser).where(PremiumUser.telegram_user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        await session.commit()
        return True


async def is_premium_user(user_id: int) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(PremiumUser.id).where(PremiumUser.telegram_user_id == user_id)
        )
        return result.scalar_one_or_none() is not None


async def get_premium_users(limit: int = 200) -> list[PremiumUser]:
    effective_limit = max(1, min(limit, 1000))
    async with SessionLocal() as session:
        result = await session.execute(
            select(PremiumUser)
            .order_by(PremiumUser.created_at.desc(), PremiumUser.id.desc())
            .limit(effective_limit)
        )
        return list(result.scalars().all())
