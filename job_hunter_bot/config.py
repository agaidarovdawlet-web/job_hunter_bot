"""Конфигурация проекта.

Все настройки читаются из переменных окружения / файла .env с помощью
pydantic-settings. Реальные секреты (токен бота, chat_id) никогда не
хранятся в коде — только в .env (локально) или в GitHub Secrets (в CI).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from job_hunter_bot.skills import INCLUDE_KEYWORDS as SKILL_INCLUDE_KEYWORDS

BASE_DIR = Path(__file__).resolve().parent.parent

# Поисковые запросы по умолчанию.
# Чтобы добавить новый запрос — просто добавь строку в этот список
# либо передай свой список через переменную окружения SEARCH_QUERIES
# (через запятую), см. README.md -> "Как добавить новые запросы".
DEFAULT_SEARCH_QUERIES: list[str] = [
    "Junior Python Developer",
    "Junior Backend Developer",
    "Python стажер",
    "Telegram Bot Developer",
    "aiogram",
    "Технический специалист",
    "Специалист технической поддержки",
    "Helpdesk",
    "IT Support",
    "Support Engineer",
    "Младший системный администратор",
    "Junior System Administrator",
    "Системный администратор без опыта",
    "Техническая поддержка SQL",
]

# Ключевые слова, при наличии которых вакансия исключается сразу.
EXCLUDE_KEYWORDS: list[str] = [
    "senior",
    "сеньор",
    "middle+",
    "миддл+",
    "team lead",
    "тимлид",
    "team-lead",
    "lead developer",
    "ведущий разработчик",
    "head of",
    "руководитель отдела разработки",
]

# Для обратной совместимости экспортируем include-ключевые слова из единого skills.py.
INCLUDE_KEYWORDS: list[str] = SKILL_INCLUDE_KEYWORDS

class Settings(BaseSettings):
    """Настройки приложения, загружаемые из окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(default="", description="Токен Telegram-бота от @BotFather")
    telegram_chat_id: str = Field(default="", description="ID чата/пользователя для уведомлений")

    # --- HH API ---
    hh_api_base_url: str = Field(default="https://api.hh.ru/vacancies")
    hh_area: str = Field(default="113", description="Код региона hh.ru (113 = Россия)")
    hh_per_page: int = Field(default=20, ge=1, le=100)
    hh_pages_per_query: int = Field(default=1, ge=1, le=20)
    hh_max_concurrent_requests: int = Field(default=4, ge=1, le=20)
    hh_failure_alert_ratio: float = Field(default=0.5, ge=0, le=1)
    hh_user_agent: str = Field(
        default="job_hunter_bot/1.1 (contact: human-local@localhost)",
        description="hh.ru требует указывать User-Agent для API-запросов",
    )

    # --- Gemini API ---
    gemini_api_key: str = Field(
        default="",
        description="Ключ Google Gemini API для генерации черновиков отклика",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Модель Gemini для генерации текста отклика",
    )
    semantic_score_min: int = Field(
        default=45,
        ge=0,
        le=100,
        description="Нижняя граница score для semantic Gemini-переоценки",
    )
    semantic_score_max: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Верхняя граница score для semantic Gemini-переоценки",
    )
    semantic_score_weight: float = Field(
        default=0.4,
        ge=0,
        le=1,
        description="Вес semantic Gemini-оценки в финальном blended score",
    )

    # --- Поиск / фильтрация / оценка ---
    search_queries_raw: str = Field(default="", alias="SEARCH_QUERIES")
    max_experience_years: int = Field(
        default=3,
        ge=1,
        description="Опыт от N лет — исключаем вакансию",
    )
    score_threshold: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Порог для уведомления в Telegram",
    )

    # --- База данных ---
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'vacancies.db'}"
    )

    @field_validator(
        "telegram_bot_token",
        "telegram_chat_id",
        "gemini_api_key",
        "gemini_model",
        mode="before",
    )
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        if v.startswith("sqlite:///"):
            return v.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def search_queries(self) -> list[str]:
        if self.search_queries_raw.strip():
            return [q.strip() for q in self.search_queries_raw.split(",") if q.strip()]
        return DEFAULT_SEARCH_QUERIES


settings = Settings()
