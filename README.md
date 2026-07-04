# job_hunter_bot

Автоматизированный job-hunting pipeline для hh.ru: поиск вакансий, фильтрация,
релевантность `0..100`, сохранение в БД, Telegram-уведомления, FastAPI dashboard
и CI/CD-процессы для ежедневного запуска.

## Portfolio Snapshot

- `Python 3.12`, полностью `async`
- `httpx` + `SQLAlchemy 2.0 async` + `aiogram 3.x`
- `SQLite` локально / `Postgres` для production
- `Alembic` migrations
- `FastAPI` dashboard
- `GitHub Actions` для CI и scheduled search
- `Gemini` для персонализированных draft replies и semantic rescoring
- `pytest`, `ruff`, `mypy`

## What This Project Solves

Обычный отклик на junior/support-вакансии быстро превращается в ручной шум:
одни и те же поиски, много нерелевантных senior-позиций, повторяющиеся описания
и отсутствие нормального трекинга. Этот проект превращает процесс в управляемый
пайплайн:

`HH API -> filters -> scoring -> semantic review -> DB -> Telegram -> dashboard`

На практике бот:
- ищет вакансии по нескольким запросам для `Junior Python`, `Helpdesk`,
  `IT Support` и `Junior SysAdmin`
- отбрасывает `Senior / Middle+ / Lead` и роли с завышенным порогом опыта
- считает keyword-score и при необходимости уточняет его через Gemini
- сохраняет только новые вакансии, кэширует LLM-результаты и отслеживает статус
- отправляет только релевантные вакансии в Telegram
- показывает статистику и top results через bot commands и web dashboard

## Key Features

### 1. Unified async architecture

- `httpx.AsyncClient` для HH API
- async `SQLAlchemy` sessions
- async Telegram bot и async search runner в одном event loop

### 2. Relevance pipeline instead of naive keyword search

- отдельная фильтрация уровня вакансии
- score `0..100`
- больший вес совпадений в `title`
- защита от ложных срабатываний вроде `SQL не требуется`
- защита от ложного опыта вроде `с 2021 года`
- optional semantic rescoring для пограничных вакансий

### 3. Telegram workflow for real usage

- уведомления только по новым high-score вакансиям
- `/top`, `/stats`, `/applied`, `/reject`
- inline-кнопки под вакансиями
- персонализированный draft reply с fallback на локальный шаблон

### 4. Production-minded persistence

- `SQLite` для локального режима
- `Postgres` для GitHub Actions / production
- `Alembic` вместо `create_all`
- кэш черновиков и semantic score в БД

### 5. Demo-friendly presentation layer

- FastAPI dashboard
- Docker / Docker Compose
- CI workflow для `ruff`, `mypy`, `pytest`
- scheduled workflow для daily search

## Architecture

```text
scripts/run_search.py
    -> job_hunter_bot.search_runner.run_search()
        -> HHClient.search_many()
        -> filter_vacancies()
        -> calculate_score()
        -> Gemini semantic rescoring for borderline items
        -> save_vacancy()
        -> send_vacancies()
```

Основные модули:

| Module | Responsibility |
|---|---|
| `hh_client.py` | async HH API client, retry/backoff, concurrency limit |
| `filters.py` | junior/support filtering, experience gating |
| `skills.py` | single source of truth for skill keywords and score rules |
| `scoring.py` | weighted keyword scoring |
| `llm.py` | Gemini draft generation and semantic rescoring |
| `db.py` / `crud.py` | async DB layer, statuses, persistence |
| `bot.py` / `notifier.py` | Telegram commands, notifications, inline actions |
| `web/app.py` | FastAPI dashboard |

## Tech Stack

- Python 3.12
- httpx
- SQLAlchemy 2.0 async
- aiosqlite / asyncpg
- aiogram 3.x
- FastAPI + Jinja2 + Uvicorn
- Pydantic Settings
- Alembic
- Google Gemini via `google-genai`
- pytest / pytest-asyncio
- Ruff / mypy
- Docker / Docker Compose
- GitHub Actions

## Local Run

### 1. Clone and install

```bash
git clone https://github.com/agaidarovdawlet-web/job_hunter_bot.git
cd job_hunter_bot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

По умолчанию `.env.example` настроен на локальный `SQLite`. Для production
можно переключить `DATABASE_URL` на `postgresql+asyncpg://...`.

### 3. Apply migrations

```bash
alembic upgrade head
```

### 4. Run search

```bash
python scripts/run_search.py
```

### 5. Run bot

```bash
python scripts/run_bot.py
```

### 6. Run dashboard

```bash
uvicorn job_hunter_bot.web.app:app --reload --port 8000
```

### 7. Run checks

```bash
ruff check .
mypy job_hunter_bot
pytest -q
```

## Docker

```bash
docker compose up --build bot
docker compose run --rm search
```

`docker-compose.yml` сохраняет локальные данные через bind mount `./data:/app/data`.

## Configuration

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | chat/user id for notifications |
| `DATABASE_URL` | `sqlite+aiosqlite:///...` or `postgresql+asyncpg://...` |
| `SEARCH_QUERIES` | custom comma-separated queries |
| `MAX_EXPERIENCE_YEARS` | upper experience threshold for filtering |
| `SCORE_THRESHOLD` | minimum score for Telegram notifications |
| `HH_MAX_CONCURRENT_REQUESTS` | limit for parallel HH API requests |
| `HH_FAILURE_ALERT_RATIO` | threshold for diagnostic alerts |
| `GEMINI_API_KEY` | enables LLM draft generation and semantic rescoring |
| `GEMINI_MODEL` | Gemini model name |
| `SEMANTIC_SCORE_MIN` | lower bound for semantic rescoring window |
| `SEMANTIC_SCORE_MAX` | upper bound for semantic rescoring window |
| `SEMANTIC_SCORE_WEIGHT` | semantic score weight in final blended score |

See [.env.example](.env.example) for the full template.

## Scoring Model

Base score uses skill rules from [job_hunter_bot/skills.py](job_hunter_bot/skills.py):

- `Python` -> `+20`
- `SQL` -> `+15`
- `Linux` -> `+15`
- `Git` -> `+15`
- `Docker` -> `+10`
- `FastAPI / Django / Flask` -> `+10`
- `Support / Helpdesk` -> `+10`
- `Remote` -> `+10`
- `3+ years experience` -> `-30`
- `Senior / Middle / Lead` -> `-50`

Дополнительно:
- совпадения в `title` получают bonus поверх обычного score
- отрицания рядом с keyword не добавляют баллы
- для score в диапазоне `SEMANTIC_SCORE_MIN..SEMANTIC_SCORE_MAX`
  может применяться Gemini-based rescoring

## Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` | intro and commands |
| `/top [N]` | top vacancies by score |
| `/stats` | total stats and score distribution |
| `/applied <id>` | mark as applied |
| `/reject <id>` | mark as rejected |

Inline buttons duplicate the same status actions directly from vacancy cards.

## Dashboard

FastAPI dashboard shows:
- top saved vacancies
- aggregate stats
- browser-friendly demo surface for interviews and portfolio review

Run locally:

```bash
uvicorn job_hunter_bot.web.app:app --reload --port 8000
```

## CI / Automation

- `.github/workflows/ci.yml` runs `ruff`, `mypy`, `pytest`
- `.github/workflows/job_search.yml` runs scheduled search daily at `08:00 UTC`
- both workflows use timeouts
- production path is migration-first via `alembic upgrade head`

## Project Structure

```text
job_hunter_bot/
├── job_hunter_bot/
│   ├── bot.py
│   ├── candidate_profile.py
│   ├── config.py
│   ├── crud.py
│   ├── db.py
│   ├── filters.py
│   ├── formatting.py
│   ├── hh_client.py
│   ├── llm.py
│   ├── notifier.py
│   ├── scoring.py
│   ├── search_runner.py
│   ├── skills.py
│   └── web/
├── migrations/
├── scripts/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Security Notes

- реальные токены не хранятся в репозитории
- `.env` исключён из git и Docker build context
- локальная SQLite база не коммитится
- GitHub Actions используют secrets для production credentials

## Roadmap Ideas

- dashboard auth + filters
- heartbeat notifications on long no-result streaks
- multi-source job adapters besides hh.ru
- stronger deduplication beyond raw URL

## License

MIT. See [LICENSE](LICENSE).
