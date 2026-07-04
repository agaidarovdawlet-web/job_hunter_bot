"""Telegram-бот (aiogram 3.x) с командами и инлайн-кнопками.

Запускается отдельно (long polling), в отличие от search_runner.py, который
запускается по расписанию через GitHub Actions. См. README.md.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter_bot.config import settings
from job_hunter_bot.crud import get_by_id, get_stats, get_top, set_status
from job_hunter_bot.db import Vacancy, VacancyStatus, get_session, init_db
from job_hunter_bot.formatting import format_telegram_message
from job_hunter_bot.llm import get_or_create_cached_draft

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

dp = Dispatcher()


def vacancy_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Откликнулся",
                    callback_data=f"applied:{vacancy_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{vacancy_id}",
                ),
            ]
        ]
    )


async def send_vacancy_message(
    message: Message,
    vacancy: Vacancy,
    session: AsyncSession,
) -> None:
    draft_text = await get_or_create_cached_draft(session, vacancy)
    await message.answer(
        format_telegram_message(vacancy, draft_text=draft_text),
        reply_markup=vacancy_keyboard(vacancy.id),
    )


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я job_hunter_bot — помогаю искать вакансии Junior Python / "
        "Android / IT Support / Helpdesk / Junior SysAdmin на hh.ru.\n\n"
        "Доступные команды:\n"
        "/top [N] — топ вакансий по score (по умолчанию 5)\n"
        "/stats — статистика по найденным вакансиям\n"
        "/applied <id> — отметить, что откликнулся\n"
        "/reject <id> — отклонить вакансию\n\n"
        "Под карточками вакансий есть кнопки для быстрого обновления статуса."
    )


@dp.message(Command("top"))
async def cmd_top(message: Message, command: CommandObject) -> None:
    limit = 5
    if command.args and command.args.strip().isdigit():
        limit = max(1, min(20, int(command.args.strip())))

    session = get_session()
    try:
        vacancies = await get_top(session, limit=limit)
        if not vacancies:
            await message.answer(
                "Пока нет сохранённых вакансий. "
                "Запусти поиск (search_runner.py)."
            )
            return

        await message.answer(f"🏆 Топ {len(vacancies)} вакансий:")
        for vacancy in vacancies:
            await send_vacancy_message(message, vacancy, session)
        await session.commit()
    finally:
        await session.close()


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    session = get_session()
    try:
        stats = await get_stats(session)
    finally:
        await session.close()

    text = (
        "📊 <b>Статистика по вакансиям</b>\n\n"
        f"Всего найдено: <b>{stats['total']}</b>\n"
        f"🆕 Новых: {stats['new']}\n"
        f"👀 Просмотрено: {stats['viewed']}\n"
        f"✅ Откликнулся: {stats['applied']}\n"
        f"❌ Отклонено: {stats['rejected']}\n\n"
        f"⭐ Средний score: {stats['avg_score']}\n"
        f"🎯 Со score ≥ 60: {stats['high_score']}\n"
        f"🏠 Удалённых: {stats['remote']}"
    )
    await message.answer(text)


@dp.message(Command("applied"))
async def cmd_applied(message: Message, command: CommandObject) -> None:
    await _set_status_command(
        message,
        command,
        VacancyStatus.APPLIED,
        "✅ Отмечено как «откликнулся»",
    )


@dp.message(Command("reject"))
async def cmd_reject(message: Message, command: CommandObject) -> None:
    await _set_status_command(message, command, VacancyStatus.REJECTED, "❌ Вакансия отклонена")


@dp.callback_query(F.data.startswith("applied:") | F.data.startswith("reject:"))
async def cb_set_status(callback: CallbackQuery) -> None:
    if not callback.data:
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return

    action, vacancy_id_str = callback.data.split(":", 1)
    if not vacancy_id_str.isdigit():
        await callback.answer("Некорректный ID вакансии.", show_alert=True)
        return

    status = (
        VacancyStatus.APPLIED if action == "applied" else VacancyStatus.REJECTED
    )
    ok_text = (
        "✅ Статус обновлён: откликнулся"
        if status == VacancyStatus.APPLIED
        else "❌ Статус обновлён: отклонена"
    )

    updated = await _update_vacancy_status(int(vacancy_id_str), status)
    if updated is None:
        await callback.answer("Вакансия не найдена.", show_alert=True)
        return

    await callback.answer(ok_text)
    if callback.message is not None and not isinstance(
        callback.message,
        InaccessibleMessage,
    ):
        await callback.message.edit_reply_markup(reply_markup=None)


async def _set_status_command(
    message: Message, command: CommandObject, status: VacancyStatus, ok_text: str
) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Укажи ID вакансии, например: <code>/applied 42</code>")
        return

    vacancy_id = int(command.args.strip())
    vacancy = await _update_vacancy_status(vacancy_id, status)
    if vacancy is None:
        await message.answer(f"Вакансия с ID {vacancy_id} не найдена.")
        return

    await message.answer(f"{ok_text}: «{vacancy.title}» (ID {vacancy_id})")


async def _update_vacancy_status(
    vacancy_id: int,
    status: VacancyStatus,
) -> Vacancy | None:
    session = get_session()
    try:
        vacancy = await get_by_id(session, vacancy_id)
        if vacancy is None:
            return None
        await set_status(session, vacancy_id, status)
        await session.commit()
        return vacancy
    finally:
        await session.close()


async def main() -> None:
    await init_db()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN не задан. Проверь .env / GitHub Secrets."
        )

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
