from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, select, text
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
