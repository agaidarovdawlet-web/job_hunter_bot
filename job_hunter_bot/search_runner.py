"""Оркестрация поиска: HH API -> фильтрация -> scoring -> сохранение -> Telegram."""
from __future__ import annotations

import logging

from job_hunter_bot.config import settings
from job_hunter_bot.crud import save_vacancy
from job_hunter_bot.db import get_session, init_db
from job_hunter_bot.filters import filter_vacancies
from job_hunter_bot.hh_client import HHClient
from job_hunter_bot.llm import blend_scores, get_or_create_semantic_score
from job_hunter_bot.notifier import send_diagnostic_message, send_vacancies
from job_hunter_bot.scoring import calculate_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_search() -> None:
    """Полный цикл: ищет вакансии по всем запросам, фильтрует, считает score,
    сохраняет новые в БД и отправляет в Telegram те, у кого score >= порога.
    """
    await init_db()

    logger.info("Starting search for %d queries", len(settings.search_queries))
    async with HHClient() as client:
        search_result = await client.search_many(settings.search_queries)
    raw_vacancies = search_result.vacancies
    logger.info("Fetched %d raw vacancies", len(raw_vacancies))

    if raw_vacancies == [] or search_result.failure_ratio >= settings.hh_failure_alert_ratio:
        failed_queries_text = ", ".join(
            f"{query} ({count})" for query, count in search_result.failed_queries.items()
        ) or "нет"
        diagnostic_text = (
            "<b>job_hunter_bot diagnostic</b>\n"
            f"Сырых вакансий получено: <b>{len(raw_vacancies)}</b>\n"
            f"Неудачных запросов: <b>{search_result.failed_requests}</b> "
            f"из <b>{search_result.attempted_requests}</b>\n"
            f"Failure ratio: <b>{search_result.failure_ratio:.2f}</b>\n"
            f"Порог оповещения: <b>{settings.hh_failure_alert_ratio:.2f}</b>\n"
            f"Проблемные query: <b>{failed_queries_text}</b>"
        )
        await send_diagnostic_message(diagnostic_text)

    relevant = filter_vacancies(raw_vacancies)
    logger.info("%d vacancies passed filters", len(relevant))

    new_high_score = []
    session = get_session()
    try:
        seen_urls: set[str] = set()
        saved_count = 0
        for raw in relevant:
            if raw.url in seen_urls:
                continue
            seen_urls.add(raw.url)

            base_score = calculate_score(raw)
            vacancy = await save_vacancy(session, raw, base_score)
            if vacancy is None:
                continue  # дубликат, уже есть в базе

            final_score = base_score
            if settings.semantic_score_min <= base_score <= settings.semantic_score_max:
                semantic_score = await get_or_create_semantic_score(session, vacancy)
                if semantic_score is not None:
                    final_score = blend_scores(base_score, semantic_score)
                    vacancy.score = final_score

            saved_count += 1
            if final_score >= settings.score_threshold:
                new_high_score.append(vacancy)

        await session.commit()
        logger.info(
            "Saved %d new vacancies, %d of them with score >= %d",
            saved_count,
            len(new_high_score),
            settings.score_threshold,
        )
    finally:
        await session.close()

    await send_vacancies(new_high_score)
    logger.info("Done.")
