from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import BigInteger, Integer, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DB_PATH = Path(__file__).resolve().parents[1] / "bot.sqlite3"


class Base(DeclarativeBase):
    pass


class UserBalance(Base):
    __tablename__ = "user_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=10)


engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_or_create_user_tokens(user_id: int, default_tokens: int = 10) -> int:
    with get_session() as session:
        user = session.execute(
            select(UserBalance).where(UserBalance.telegram_user_id == user_id)
        ).scalar_one_or_none()
        if user is None:
            user = UserBalance(telegram_user_id=user_id, tokens=default_tokens)
            session.add(user)
            session.flush()
        return user.tokens


def try_spend_user_token(user_id: int, default_tokens: int = 10) -> tuple[bool, int]:
    with get_session() as session:
        user = session.execute(
            select(UserBalance).where(UserBalance.telegram_user_id == user_id)
        ).scalar_one_or_none()
        if user is None:
            user = UserBalance(telegram_user_id=user_id, tokens=default_tokens)
            session.add(user)
            session.flush()
        if user.tokens <= 0:
            return False, user.tokens
        user.tokens -= 1
        session.flush()
        return True, user.tokens


def add_user_tokens(user_id: int, amount: int, default_tokens: int = 10) -> int:
    with get_session() as session:
        user = session.execute(
            select(UserBalance).where(UserBalance.telegram_user_id == user_id)
        ).scalar_one_or_none()
        if user is None:
            user = UserBalance(telegram_user_id=user_id, tokens=default_tokens)
            session.add(user)
            session.flush()
        user.tokens += amount
        session.flush()
        return user.tokens


def set_user_tokens(user_id: int, amount: int, default_tokens: int = 10) -> int:
    with get_session() as session:
        user = session.execute(
            select(UserBalance).where(UserBalance.telegram_user_id == user_id)
        ).scalar_one_or_none()
        if user is None:
            user = UserBalance(telegram_user_id=user_id, tokens=default_tokens)
            session.add(user)
            session.flush()
        user.tokens = amount
        session.flush()
        return user.tokens
