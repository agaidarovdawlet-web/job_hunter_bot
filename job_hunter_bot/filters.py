"""Фильтрация вакансий: исключаем Senior/Middle+/Lead и вакансии с опытом 3+ года,
оставляем junior / intern / стажёр / без опыта / support / helpdesk / sysadmin.
"""
from __future__ import annotations

import re

from job_hunter_bot.config import EXCLUDE_KEYWORDS, settings
from job_hunter_bot.hh_client import RawVacancy
from job_hunter_bot.skills import FILTER_SKILLS, matches_skill

_EXPERIENCE_CONTEXT_RE = re.compile(
    r"\bопыт(?:\s+\w+){0,4}\s*(?:от|не менее)\s*(\d+)\s*\+?\s*(?:лет|года|год)\b",
    re.IGNORECASE,
)
_YEARS_OF_EXPERIENCE_RE = re.compile(
    r"\b(\d+)\s*\+?\s*(?:лет|года|год)\s+опыта\b",
    re.IGNORECASE,
)

_HH_EXPERIENCE_RE = re.compile(r"(\d+)")


def _text_blob(v: RawVacancy) -> str:
    return " ".join([v.title, v.requirements, v.experience, v.schedule]).lower()


def _include_blob(v: RawVacancy) -> str:
    return " ".join([v.title, v.requirements, v.schedule]).lower()


def has_excluded_keyword(v: RawVacancy) -> bool:
    blob = _text_blob(v)
    return any(kw in blob for kw in EXCLUDE_KEYWORDS)


def _min_years_from_hh_experience(experience_name: str) -> int | None:
    normalized = experience_name.strip().lower()
    if not normalized or normalized == "нет опыта":
        return None
    if normalized.startswith("более "):
        match = _HH_EXPERIENCE_RE.search(normalized)
        if match:
            return int(match.group(1)) + 1
        return None
    if normalized.startswith("от "):
        match = _HH_EXPERIENCE_RE.search(normalized)
        if match:
            return int(match.group(1))
    return None


def requires_3plus_years(v: RawVacancy) -> bool:
    if (min_years := _min_years_from_hh_experience(v.experience)) is not None:
        return min_years >= settings.max_experience_years

    blob = _text_blob(v)
    for pattern in (_EXPERIENCE_CONTEXT_RE, _YEARS_OF_EXPERIENCE_RE):
        for match in pattern.finditer(blob):
            years = int(match.group(1))
            if years >= settings.max_experience_years:
                return True
    return False


def has_included_keyword(v: RawVacancy) -> bool:
    blob = _include_blob(v)
    # "Нет опыта" считаем достаточным сигналом junior/intern уровня.
    if v.experience.lower() == "нет опыта":
        return True
    return any(matches_skill(blob, skill) for skill in FILTER_SKILLS)


def is_relevant(v: RawVacancy) -> bool:
    """Главная функция фильтрации. Возвращает True, если вакансию стоит сохранить."""
    if has_excluded_keyword(v):
        return False
    if requires_3plus_years(v):
        return False
    return has_included_keyword(v)


def filter_vacancies(vacancies: list[RawVacancy]) -> list[RawVacancy]:
    return [v for v in vacancies if is_relevant(v)]
