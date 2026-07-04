"""Формирование текста Telegram-сообщений и черновиков откликов."""
from __future__ import annotations

from job_hunter_bot.candidate_profile import (
    CANDIDATE_PROFILE_DRAFT_INTRO,
    CANDIDATE_PROFILE_TARGET_ROLES,
)
from job_hunter_bot.db import Vacancy
from job_hunter_bot.skills import REASON_SKILLS, matching_skills


def why_it_fits(vacancy: Vacancy) -> str:
    blob = f"{vacancy.title} {vacancy.requirements}".lower()
    reasons = [skill.reason for skill in matching_skills(blob, REASON_SKILLS)]
    if vacancy.remote:
        reasons.append("можно работать удалённо")
    if not reasons:
        reasons.append("подходит по уровню (junior/без опыта)")
    # убираем дубликаты, сохраняя порядок
    seen: set[str] = set()
    unique = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return "; ".join(unique)


def draft_reply(vacancy: Vacancy) -> str:
    """Генерирует короткий черновик отклика на вакансию."""
    return (
        f"Здравствуйте!\n\n"
        f"Меня заинтересовала вакансия «{vacancy.title}» в компании {vacancy.company}. "
        f"{CANDIDATE_PROFILE_DRAFT_INTRO} "
        f"{CANDIDATE_PROFILE_TARGET_ROLES}\n\n"
        f"Буду рад обсудить, чем могу быть полезен вашей команде.\n\n"
        f"С уважением!"
    )


def format_telegram_message(vacancy: Vacancy, draft_text: str | None = None) -> str:
    """Форматирует сообщение о вакансии для отправки в Telegram (см. п.8 ТЗ)."""
    remote_label = "Удалённо" if vacancy.remote else "Офис / см. описание"
    salary = vacancy.salary or "Не указана"
    draft = draft_text or draft_reply(vacancy)

    return (
        f"🎯 <b>{vacancy.title}</b>\n"
        f"🏢 {vacancy.company}\n"
        f"💰 {salary}\n"
        f"📍 {remote_label} · {vacancy.city or '—'}\n"
        f"⭐ Score: <b>{vacancy.score}/100</b>\n\n"
        f"✅ <i>Почему подходит:</i> {why_it_fits(vacancy)}\n\n"
        f"🔗 {vacancy.url}\n\n"
        f"✏️ <b>Черновик отклика:</b>\n{draft}\n\n"
        f"ID в базе: <code>{vacancy.id}</code>"
    )
