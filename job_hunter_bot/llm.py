"""Генерация черновика отклика через Google Gemini с безопасным fallback."""
from __future__ import annotations

import asyncio
import re

from google import genai  # type: ignore[attr-defined]
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter_bot.candidate_profile import CANDIDATE_PROFILE_SUMMARY
from job_hunter_bot.config import settings
from job_hunter_bot.db import Vacancy
from job_hunter_bot.formatting import draft_reply

_SEMANTIC_SCORE_RE = re.compile(r"\b([0-9]{1,3})\b")


def _extract_score(text: str) -> int | None:
    match = _SEMANTIC_SCORE_RE.search(text)
    if not match:
        return None
    score = int(match.group(1))
    if 0 <= score <= 100:
        return score
    return None


def blend_scores(base_score: int, semantic_score: int) -> int:
    weight = settings.semantic_score_weight
    blended = round((base_score * (1 - weight)) + (semantic_score * weight))
    return max(0, min(100, blended))


async def generate_draft_reply(vacancy: Vacancy) -> str:
    """Генерирует персонализированный отклик через Gemini.

    Если ключ не задан или API вернул ошибку, возвращает шаблонный текст.
    """
    if not settings.gemini_api_key:
        return draft_reply(vacancy)

    prompt = (
        f"Напиши короткий отклик на вакансию «{vacancy.title}» в компании "
        f"{vacancy.company}. Используй 5-7 предложений, тон вежливый, по делу, "
        f"без воды. Только текст письма без заголовков и пояснений. "
        f"Требования вакансии: {vacancy.requirements[:500]}. "
        f"Мой профиль: {CANDIDATE_PROFILE_SUMMARY}"
    )

    try:
        async with genai.Client(api_key=settings.gemini_api_key).aio as client:
            response = await asyncio.wait_for(
                client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                ),
                timeout=15,
            )
    except (TimeoutError, Exception):
        return draft_reply(vacancy)

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    return draft_reply(vacancy)


async def get_or_create_cached_draft(
    session: AsyncSession,
    vacancy: Vacancy,
) -> str:
    """Возвращает кэшированный черновик или генерирует и сохраняет новый."""
    if vacancy.draft_reply_cached.strip():
        return vacancy.draft_reply_cached

    generated = await generate_draft_reply(vacancy)
    vacancy.draft_reply_cached = generated
    await session.flush()
    return generated


async def generate_semantic_score(vacancy: Vacancy) -> int | None:
    """Просит Gemini оценить релевантность вакансии профилю кандидата."""
    if not settings.gemini_api_key:
        return None

    prompt = (
        "Оцени релевантность вакансии профилю кандидата по шкале от 0 до 100. "
        "Верни только одно целое число без пояснений.\n"
        f"Профиль кандидата: {CANDIDATE_PROFILE_SUMMARY}\n"
        f"Вакансия: {vacancy.title}\n"
        f"Компания: {vacancy.company}\n"
        f"Требования: {vacancy.requirements[:800]}"
    )

    try:
        async with genai.Client(api_key=settings.gemini_api_key).aio as client:
            response = await asyncio.wait_for(
                client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                ),
                timeout=15,
            )
    except (TimeoutError, Exception):
        return None

    text = getattr(response, "text", None)
    if not isinstance(text, str):
        return None
    return _extract_score(text.strip())


async def get_or_create_semantic_score(
    session: AsyncSession,
    vacancy: Vacancy,
) -> int | None:
    """Возвращает кэшированную semantic-оценку или сохраняет новую."""
    if vacancy.semantic_score_cached is not None:
        return vacancy.semantic_score_cached

    generated = await generate_semantic_score(vacancy)
    if generated is None:
        return None

    vacancy.semantic_score_cached = generated
    await session.flush()
    return generated
