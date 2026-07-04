from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from job_hunter_bot import llm
from job_hunter_bot.crud import save_vacancy
from job_hunter_bot.db import Base
from job_hunter_bot.hh_client import RawVacancy


def make_raw_vacancy(url: str = "https://example.com/vacancy/cache") -> RawVacancy:
    return RawVacancy(
        external_id="ext-cache",
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
async def test_get_or_create_cached_draft_reuses_saved_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'draft-cache.db'}"
    engine = create_async_engine(db_url, future=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    calls = 0

    async def fake_generate(vacancy) -> str:
        nonlocal calls
        calls += 1
        return f"cached draft for {vacancy.title}"

    monkeypatch.setattr(llm, "generate_draft_reply", fake_generate)

    async with session_factory() as session:
        vacancy = await save_vacancy(session, make_raw_vacancy(), score=90)
        assert vacancy is not None

        first = await llm.get_or_create_cached_draft(session, vacancy)
        second = await llm.get_or_create_cached_draft(session, vacancy)

        assert first == second
        assert first == "cached draft for Junior Python Developer"
        assert vacancy.draft_reply_cached == first
        assert calls == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_or_create_semantic_score_reuses_saved_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'semantic-cache.db'}"
    engine = create_async_engine(db_url, future=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    calls = 0

    async def fake_generate(vacancy) -> int | None:
        nonlocal calls
        calls += 1
        return 77

    monkeypatch.setattr(llm, "generate_semantic_score", fake_generate)

    async with session_factory() as session:
        vacancy = await save_vacancy(session, make_raw_vacancy(), score=60)
        assert vacancy is not None

        first = await llm.get_or_create_semantic_score(session, vacancy)
        second = await llm.get_or_create_semantic_score(session, vacancy)

        assert first == second == 77
        assert vacancy.semantic_score_cached == 77
        assert calls == 1

    await engine.dispose()
