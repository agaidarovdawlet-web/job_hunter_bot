"""Операции с базой данных: сохранение вакансий, выборки, обновление статуса."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter_bot.db import Vacancy, VacancyStatus
from job_hunter_bot.hh_client import RawVacancy


async def vacancy_exists(session: AsyncSession, url: str) -> bool:
    stmt = select(Vacancy.id).where(Vacancy.url == url)
    result = await session.execute(stmt)
    return result.first() is not None


async def save_vacancy(
    session: AsyncSession,
    raw: RawVacancy,
    score: int,
) -> Vacancy | None:
    """Сохраняет вакансию, если такого url ещё нет в базе. Возвращает объект,
    если вакансия новая, либо None, если это дубликат."""
    if await vacancy_exists(session, raw.url):
        return None

    vacancy = Vacancy(
        external_id=raw.external_id,
        title=raw.title,
        company=raw.company,
        salary=raw.salary,
        city=raw.city,
        remote=raw.remote,
        url=raw.url,
        requirements=raw.requirements[:4000],
        score=score,
        source=raw.source,
        status=VacancyStatus.NEW.value,
    )
    session.add(vacancy)
    await session.flush()
    return vacancy


async def get_top(session: AsyncSession, limit: int = 10) -> list[Vacancy]:
    stmt = (
        select(Vacancy)
        .where(Vacancy.status != VacancyStatus.REJECTED.value)
        .order_by(Vacancy.score.desc(), Vacancy.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, vacancy_id: int) -> Vacancy | None:
    return await session.get(Vacancy, vacancy_id)


async def set_status(
    session: AsyncSession,
    vacancy_id: int,
    status: VacancyStatus,
) -> Vacancy | None:
    vacancy = await get_by_id(session, vacancy_id)
    if vacancy is None:
        return None
    vacancy.status = status.value
    await session.flush()
    return vacancy


async def get_stats(session: AsyncSession) -> dict[str, int | float]:
    total = (await session.execute(select(func.count(Vacancy.id)))).scalar_one()

    by_status_result = await session.execute(
        select(Vacancy.status, func.count(Vacancy.id)).group_by(Vacancy.status)
    )
    by_status: dict[str, int] = {
        status: count for status, count in by_status_result.all()
    }

    avg_score = (await session.execute(select(func.avg(Vacancy.score)))).scalar_one() or 0
    remote_count = (
        await session.execute(
        select(func.count(Vacancy.id)).where(Vacancy.remote.is_(True))
        )
    ).scalar_one()
    high_score_count = (
        await session.execute(
        select(func.count(Vacancy.id)).where(Vacancy.score >= 60)
        )
    ).scalar_one()

    return {
        "total": total,
        "new": by_status.get(VacancyStatus.NEW.value, 0),
        "viewed": by_status.get(VacancyStatus.VIEWED.value, 0),
        "applied": by_status.get(VacancyStatus.APPLIED.value, 0),
        "rejected": by_status.get(VacancyStatus.REJECTED.value, 0),
        "avg_score": round(float(avg_score), 1),
        "remote": remote_count,
        "high_score": high_score_count,
    }
