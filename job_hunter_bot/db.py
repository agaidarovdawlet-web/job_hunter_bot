"""Модели SQLAlchemy и работа с async БД."""
from __future__ import annotations

import asyncio
import enum
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from job_hunter_bot.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


class VacancyStatus(str, enum.Enum):
    NEW = "new"
    VIEWED = "viewed"
    APPLIED = "applied"
    REJECTED = "rejected"


class Vacancy(Base):
    """Вакансия, сохранённая в базе."""

    __tablename__ = "vacancies"
    __table_args__ = (UniqueConstraint("url", name="uq_vacancy_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(512), default="")
    salary: Mapped[str] = mapped_column(String(128), default="Не указана")
    city: Mapped[str] = mapped_column(String(128), default="")
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(String(1024))
    requirements: Mapped[str] = mapped_column(Text, default="")
    draft_reply_cached: Mapped[str] = mapped_column(Text, default="")
    semantic_score_cached: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(64), default="hh.ru")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )
    status: Mapped[str] = mapped_column(String(16), default=VacancyStatus.NEW.value)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vacancy id={self.id} title={self.title!r} score={self.score}>"


_engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False)


def _sqlite_db_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite+aiosqlite:///"):
        return None
    return Path(database_url.replace("sqlite+aiosqlite:///", "", 1))


def ensure_database_path() -> None:
    db_path = _sqlite_db_path(settings.database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)


def _alembic_config() -> Config:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


async def _detect_legacy_revision() -> str | None:
    def sync_detect(sync_conn) -> str | None:
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "alembic_version" in tables or "vacancies" not in tables:
            return None

        column_names = {
            column["name"]
            for column in inspector.get_columns("vacancies")
        }
        if "draft_reply_cached" in column_names:
            if "semantic_score_cached" in column_names:
                return "20260704_0003"
            return "20260704_0002"
        return "20260703_0001"

    async with _engine.begin() as conn:
        return await conn.run_sync(sync_detect)


async def init_db() -> None:
    """Применяет Alembic-миграции. Runtime больше не использует create_all."""
    ensure_database_path()
    if legacy_revision := await _detect_legacy_revision():
        await asyncio.to_thread(command.stamp, _alembic_config(), legacy_revision)
    await asyncio.to_thread(command.upgrade, _alembic_config(), "head")


def get_session() -> AsyncSession:
    return AsyncSessionLocal()
