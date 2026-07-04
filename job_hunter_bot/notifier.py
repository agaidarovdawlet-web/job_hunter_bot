"""Отправка уведомлений о новых вакансиях в Telegram."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from job_hunter_bot.bot import vacancy_keyboard
from job_hunter_bot.config import settings
from job_hunter_bot.crud import get_by_id
from job_hunter_bot.db import Vacancy, get_session
from job_hunter_bot.formatting import format_telegram_message
from job_hunter_bot.llm import get_or_create_cached_draft

logger = logging.getLogger(__name__)


async def send_diagnostic_message(text: str) -> None:
    """Отправляет диагностическое сообщение в Telegram, если чат настроен."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Diagnostic message skipped: Telegram settings are missing.")
        return

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        await bot.send_message(chat_id=settings.telegram_chat_id, text=text)
    except TelegramAPIError as exc:
        logger.error("Failed to send diagnostic message: %s", exc)
    finally:
        await bot.session.close()


async def send_vacancies(vacancies: list[Vacancy]) -> None:
    """Отправляет список вакансий в Telegram-чат, указанный в настройках."""
    if not vacancies:
        logger.info("No new high-score vacancies to send.")
        return

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — уведомления не отправлены."
        )
        return

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    session = get_session()
    try:
        for vacancy in vacancies:
            persisted_vacancy = await get_by_id(session, vacancy.id) or vacancy
            draft_text = await get_or_create_cached_draft(session, persisted_vacancy)
            text = format_telegram_message(persisted_vacancy, draft_text=draft_text)
            try:
                await bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=text,
                    reply_markup=vacancy_keyboard(persisted_vacancy.id),
                )
            except TelegramAPIError as exc:
                logger.error("Failed to send vacancy id=%s: %s", persisted_vacancy.id, exc)
            await asyncio.sleep(0.5)  # не спамим API Telegram
        await session.commit()
    finally:
        await session.close()
        await bot.session.close()
