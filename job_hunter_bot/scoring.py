"""Расчёт релевантности вакансии (score от 0 до 100).

Правила (см. README.md -> "Как работает scoring"):
    +20  Python
    +15  SQL
    +15  Linux
    +15  Git
    +10  Docker
    +10  FastAPI / Django
    +10  техническая поддержка / helpdesk
    +10  можно удалённо
    -30  требуется опыт 3+ года
    -50  Senior / Middle / Lead
"""
from __future__ import annotations

from job_hunter_bot.filters import has_excluded_keyword, requires_3plus_years
from job_hunter_bot.hh_client import RawVacancy
from job_hunter_bot.skills import SCORING_SKILLS, matches_skill

TITLE_BONUS_WEIGHT = 0.25


def _weighted_skill_points(vacancy: RawVacancy) -> int:
    title_blob = vacancy.title.lower()
    requirements_blob = vacancy.requirements.lower()
    points = 0

    for skill in SCORING_SKILLS:
        if matches_skill(title_blob, skill):
            points += skill.score + max(1, round(skill.score * TITLE_BONUS_WEIGHT))
            continue
        if matches_skill(requirements_blob, skill):
            points += skill.score

    return points


def calculate_score(v: RawVacancy) -> int:
    """Считает score вакансии на основе текста требований/названия и признака remote."""
    score = _weighted_skill_points(v)

    if v.remote:
        score += 10

    if requires_3plus_years(v):
        score -= 30

    if has_excluded_keyword(v):
        score -= 50

    return max(0, min(100, score))
