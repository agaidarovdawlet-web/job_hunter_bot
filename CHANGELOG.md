# Changelog

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Изменено
- Runtime переведён на Alembic-first и больше не создаёт схему через `create_all`.
- Docker build теперь исключает `.env` и `.env.*`, чтобы локальные секреты не попадали в образ.
- Локальный и CI install path унифицирован вокруг `pip install -e .` / `pip install -e ".[dev]"`.
- Порог фильтрации по опыту теперь реально берётся из `MAX_EXPERIENCE_YEARS`.
- Для HH API добавлены ограничение параллелизма и диагностические уведомления при массовых сбоях или нуле результатов.
- Вызовы Gemini теперь ограничены по времени с fallback на шаблонный черновик.
- Ключевые слова навыков и score-правила вынесены в единый `skills.py`, который используют фильтрация, scoring и текст `Почему подходит`.
- Для пограничных вакансий добавлена semantic Gemini-оценка с кэшем в БД и blended score поверх keyword-scoring.
- Профиль соискателя вынесен в единый `candidate_profile.py` для шаблонов и LLM-промптов.

### Исправлено
- В Docker Compose добавлены bind mounts для `./data`, чтобы SQLite не терялась при пересборке контейнеров.
- В GitHub Actions добавлены `timeout-minutes`, чтобы зависшие job не расходовали лимиты часами.
- Добавлены полноценные тесты на парсинг HH API, retry/backoff и остановку пагинации.
- Скоринг и фильтрация теперь учитывают простые отрицания рядом с keyword и не путают `с 2021 года` с требованием `опыт от N лет`.

## [1.0.0] - 2026-07-02

### Добавлено
- Получение вакансий через публичный HH API (`hh_client.py`) по 14 поисковым запросам.
- Фильтрация вакансий по уровню (junior/intern/без опыта/support) с исключением
  Senior/Middle+/Lead и вакансий с опытом от 3 лет (`filters.py`).
- Расчёт score вакансии от 0 до 100 на основе стека и условий (`scoring.py`).
- Хранение вакансий в SQLite через SQLAlchemy с защитой от дубликатов (`db.py`, `crud.py`).
- Telegram-бот на aiogram 3.x с командами `/top`, `/stats`, `/applied`, `/reject` (`bot.py`).
- Автоматическая отправка новых вакансий со score ≥ 60 в Telegram (`notifier.py`).
- Генерация черновика отклика для каждой вакансии (`formatting.py`).
- GitHub Actions workflow: ежедневный запуск в 08:00 UTC + запуск вручную.
- Конфигурация через Pydantic Settings и `.env` (`config.py`).
- Базовые unit-тесты для фильтрации и scoring (`tests/`).
- README, LICENSE (MIT), `.env.example`.
