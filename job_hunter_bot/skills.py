"""Единый каталог skill-ключевых слов для фильтрации, scoring и пояснений."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillRule:
    id: str
    keywords: tuple[str, ...]
    score: int = 0
    reason: str = ""
    include_in_filter: bool = False


SKILLS: tuple[SkillRule, ...] = (
    SkillRule(
        id="junior_level",
        keywords=(
            "junior",
            "джуниор",
            "джун",
            "intern",
            "стажер",
            "стажёр",
            "без опыта",
            "1 год",
            "до 1 года",
        ),
        include_in_filter=True,
    ),
    SkillRule(
        id="support",
        keywords=("support", "поддержк", "helpdesk", "хелпдеск"),
        score=10,
        reason="подходит по опыту в поддержке/helpdesk",
        include_in_filter=True,
    ),
    SkillRule(
        id="sysadmin",
        keywords=("sysadmin", "системный администратор"),
        reason="подходит по роли junior sysadmin",
        include_in_filter=True,
    ),
    SkillRule(
        id="python",
        keywords=("python", "питон"),
        score=20,
        reason="есть Python",
    ),
    SkillRule(
        id="sql",
        keywords=("sql", "postgres", "mysql", "sqlite"),
        score=15,
        reason="требуется SQL",
    ),
    SkillRule(
        id="linux",
        keywords=("linux", "unix", "линукс"),
        score=15,
        reason="требуется Linux",
    ),
    SkillRule(
        id="git",
        keywords=("git", "github", "gitlab"),
        score=15,
        reason="требуется Git",
    ),
    SkillRule(
        id="docker",
        keywords=("docker", "контейнер"),
        score=10,
        reason="требуется Docker",
    ),
    SkillRule(
        id="framework",
        keywords=("fastapi", "django", "flask"),
        score=10,
        reason="требуется backend framework",
    ),
)


FILTER_SKILLS: tuple[SkillRule, ...] = tuple(skill for skill in SKILLS if skill.include_in_filter)
SCORING_SKILLS: tuple[SkillRule, ...] = tuple(skill for skill in SKILLS if skill.score > 0)
REASON_SKILLS: tuple[SkillRule, ...] = tuple(skill for skill in SKILLS if skill.reason)

_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:не требуется|не требуются|не нужен|не нужна|не нужны)$"),
    re.compile(r"(?:без|необязательно|не обязателен|не обязательна|не обязательны)$"),
)
_NEGATION_SUFFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:\s|,|:|-)*(?:не требуется|не требуются|не нужен|не нужна|не нужны)\b"),
    re.compile(
        r"^(?:\s|,|:|-)*(?:необязательно|не обязателен|не обязательна|не обязательны)\b"
    ),
)


def _find_keyword_positions(blob: str, keyword: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = blob.find(keyword, start)
        if index == -1:
            return positions
        positions.append(index)
        start = index + 1


def is_negated_match(blob: str, keyword: str, index: int) -> bool:
    prefix = blob[max(0, index - 40):index].strip()
    suffix = blob[index + len(keyword):index + len(keyword) + 40].strip()
    return any(pattern.search(prefix) for pattern in _NEGATION_PATTERNS) or any(
        pattern.search(suffix) for pattern in _NEGATION_SUFFIX_PATTERNS
    )


def has_positive_keyword(blob: str, keywords: tuple[str, ...]) -> bool:
    for keyword in keywords:
        for index in _find_keyword_positions(blob, keyword):
            if not is_negated_match(blob, keyword, index):
                return True
    return False


def matches_skill(blob: str, skill: SkillRule) -> bool:
    return has_positive_keyword(blob, skill.keywords)


def matching_skills(blob: str, skills: tuple[SkillRule, ...]) -> list[SkillRule]:
    return [skill for skill in skills if matches_skill(blob, skill)]


INCLUDE_KEYWORDS: list[str] = [
    keyword for skill in FILTER_SKILLS for keyword in skill.keywords
]
