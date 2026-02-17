from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, select, text
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


class UserTemplateCombo(Base):
    __tablename__ = "user_template_combos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    templates_csv: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


engine = create_async_engine(settings.database_url, future=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, future=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
