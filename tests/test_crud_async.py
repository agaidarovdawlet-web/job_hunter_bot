from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from job_hunter_bot.crud import (
    get_by_id,
    get_stats,
    get_top,
    save_vacancy,
    set_status,
    vacancy_exists,
)
from job_hunter_bot.db import Base, VacancyStatus
from job_hunter_bot.hh_client import RawVacancy


def make_raw_vacancy(url: str = "https://example.com/vacancy/1") -> RawVacancy:
    return RawVacancy(
        external_id="ext-1",
        title="Junior Python Developer",
        company="Example Inc",
        salary="100000 RUB",
        city="Moscow",
        remote=True,
        url=url,
        requirements="Python SQL Git Linux",
        experience="1-3 years",
        schedule="Full time",
    )


@pytest.mark.asyncio
async def test_save_vacancy_deduplicates_and_updates_status(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'crud.db'}"
    engine = create_async_engine(db_url, future=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        vacancy = await save_vacancy(session, make_raw_vacancy(), score=85)
        assert vacancy is not None
        await session.commit()

        assert await vacancy_exists(session, make_raw_vacancy().url) is True
        assert await save_vacancy(session, make_raw_vacancy(), score=85) is None

        fetched = await get_by_id(session, vacancy.id)
        assert fetched is not None
        updated = await set_status(session, vacancy.id, VacancyStatus.APPLIED)
        await session.commit()

        assert updated is not None
        assert updated.status == VacancyStatus.APPLIED.value

        stats = await get_stats(session)
        assert stats["total"] == 1
        assert stats["applied"] == 1
        assert stats["high_score"] == 1

        top = await get_top(session, limit=5)
        assert [item.id for item in top] == [vacancy.id]

    await engine.dispose()
