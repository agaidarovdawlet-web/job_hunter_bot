# job_hunter_bot 🤖

Автоматический поиск вакансий на **hh.ru** для позиций Junior Python / Android
Developer, а также технической поддержки, Helpdesk и Junior SysAdmin — с
фильтрацией, скорингом релевантности и уведомлениями в Telegram.

Проект написан на **Python 3.12**, использует **async httpx**,
**SQLAlchemy 2.0 async**, **aiogram 3.x**, **Pydantic Settings** и
запускается ежедневно через **GitHub Actions**.

---

## Что делает проект

1. Каждый день (или по запросу) ищет вакансии на hh.ru по 14 запросам:
   Junior Python Developer, Junior Backend Developer, Python стажер,
   Telegram Bot Developer, aiogram, Технический специалист, Специалист
   технической поддержки, Helpdesk, IT Support, Support Engineer, Младший
   системный администратор, Junior System Administrator, Системный
   администратор без опыта, Техническая поддержка SQL.
2. Отфильтровывает вакансии: убирает Senior / Middle+ / Lead / Team Lead и
   вакансии, где требуется опыт от `MAX_EXPERIENCE_YEARS` лет и выше;
   оставляет junior / intern / стажёр / без опыта / support / helpdesk /
   sysadmin.
3. Считает **score от 0 до 100** для каждой вакансии (см. раздел ниже).
4. Сохраняет вакансии в SQLite или Postgres, автоматически отбрасывая
   дубликаты по ссылке.
5. Отправляет в Telegram только **новые** вакансии со score ≥ 60, в формате:
   название, компания, зарплата, формат работы, score, почему подходит,
   ссылка и готовый черновик отклика. Если задан `GEMINI_API_KEY`,
   черновик персонализируется через Google Gemini; иначе используется
   локальный шаблон. Для пограничных вакансий со score в диапазоне
   `SEMANTIC_SCORE_MIN..SEMANTIC_SCORE_MAX` можно включить дополнительную
   semantic-оценку через Gemini; она кэшируется в БД и смешивается с
   keyword-score.
   Сгенерированный текст черновика тоже кэшируется в БД и повторно
   используется в `/top` и уведомлениях.
6. Через Telegram-бота можно посмотреть топ вакансий, статистику и отметить
   вакансию как «откликнулся» или «отклонена» либо командами, либо
   инлайн-кнопками прямо под карточкой вакансии.
7. Через FastAPI dashboard можно визуально просматривать статистику и топ
   сохранённых вакансий в браузере.
8. При массовых сбоях HH API или полном нуле результатов бот отправляет
   отдельное диагностическое уведомление в Telegram.

---

## Структура проекта

```
job_hunter_bot/
├── job_hunter_bot/
│   ├── config.py         # Pydantic Settings, список запросов, ключевые слова
│   ├── db.py              # async SQLAlchemy engine + модель Vacancy
│   ├── hh_client.py       # async клиент HH API (httpx.AsyncClient)
│   ├── skills.py          # единый каталог skill-ключевых слов и score-правил
│   ├── candidate_profile.py # единый профиль соискателя для шаблонов и LLM
│   ├── filters.py         # фильтрация junior/support vs senior/middle/lead
│   ├── scoring.py         # расчёт score 0-100
│   ├── crud.py            # сохранение, топ, статистика, смена статуса
│   ├── formatting.py      # текст Telegram-сообщения + черновик отклика
│   ├── notifier.py        # отправка сообщений через aiogram Bot + inline buttons
│   ├── search_runner.py   # оркестрация полного цикла поиска
│   ├── bot.py             # aiogram-бот: /top /stats /applied /reject
│   └── web/               # FastAPI dashboard + Jinja2 templates
├── scripts/
│   ├── run_search.py      # запускается по расписанию (GitHub Actions)
│   └── run_bot.py         # запуск бота (long polling), локально/на сервере
├── migrations/            # Alembic-миграции
├── tests/
│   ├── test_scoring.py
│   └── test_filters.py
├── .github/workflows/job_search.yml
├── .env.example
├── requirements.txt
├── pyproject.toml
├── LICENSE
├── CHANGELOG.md
└── README.md
```

---

## Как запустить локально

### 1. Клонировать репозиторий и создать окружение

```bash
git clone https://github.com/<your-username>/job_hunter_bot.git
cd job_hunter_bot
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e ".[dev]"
```

### 2. Настроить `.env`

```bash
cp .env.example .env
```

Открой `.env` и заполни своими значениями (см. раздел ниже, как получить
токен бота и chat_id). **Никогда не коммить `.env` в git** — он уже добавлен
в `.gitignore`.

### 3. Запустить разовый поиск вакансий

```bash
alembic upgrade head
python scripts/run_search.py
```

Это применит Alembic-миграции к базе и затем найдёт
вакансии, посчитает score, сохранит новые и отправит в Telegram те,
у кого score ≥ порога.

### 4. Запустить Telegram-бота (команды /top, /stats, /applied, /reject)

```bash
alembic upgrade head
python scripts/run_bot.py
```

Бот работает через long polling — держи процесс запущенным, пока хочешь
пользоваться командами. Для вакансий, отправленных ботом или показанных в
`/top`, доступны инлайн-кнопки `Откликнулся` / `Отклонить`.

### 5. Запустить тесты и проверки

```bash
ruff check .
mypy job_hunter_bot
pytest -q
```

### 6. Запустить веб-дашборд

```bash
alembic upgrade head
uvicorn job_hunter_bot.web.app:app --reload --port 8000
```

После запуска открой `http://127.0.0.1:8000/`.

### 7. Запуск через Docker

```bash
docker compose up --build bot
```

Разовый поиск из контейнера:

```bash
docker compose run --rm search
```

---

## Как настроить `.env`

| Переменная              | Описание                                                        |
|--------------------------|-------------------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`     | Токен бота от @BotFather                                          |
| `TELEGRAM_CHAT_ID`       | ID чата/пользователя, куда слать уведомления                     |
| `HH_API_BASE_URL`        | URL HH API (по умолчанию `https://api.hh.ru/vacancies`)          |
| `HH_AREA`                | Код региона hh.ru (`113` = Россия, см. `https://api.hh.ru/areas`) |
| `HH_PER_PAGE`            | Кол-во вакансий на странице (макс. 100)                          |
| `HH_PAGES_PER_QUERY`     | Сколько страниц запрашивать на каждый поисковый запрос            |
| `HH_MAX_CONCURRENT_REQUESTS` | Лимит одновременных HTTP-запросов к HH API                   |
| `HH_FAILURE_ALERT_RATIO` | Доля failed requests, после которой шлётся диагностическое сообщение |
| `GEMINI_API_KEY`         | Ключ Google Gemini API для генерации персонализированных откликов |
| `GEMINI_MODEL`           | Модель Gemini для черновиков отклика (`gemini-2.5-flash`)        |
| `SEMANTIC_SCORE_MIN`     | Нижняя граница score для semantic Gemini-переоценки              |
| `SEMANTIC_SCORE_MAX`     | Верхняя граница score для semantic Gemini-переоценки             |
| `SEMANTIC_SCORE_WEIGHT`  | Вес semantic Gemini-оценки в blended score                       |
| `SEARCH_QUERIES`         | (опционально) свой список запросов через запятую                  |
| `MAX_EXPERIENCE_YEARS`   | Порог по опыту, начиная с которого вакансия исключается (3)      |
| `SCORE_THRESHOLD`        | Минимальный score для отправки уведомления в Telegram (60)        |
| `DATABASE_URL`           | Async SQLAlchemy URL базы: `sqlite+aiosqlite:///...` или `postgresql+asyncpg://...` |

---

## Как подключить Telegram-бота

1. Напиши [@BotFather](https://t.me/BotFather) в Telegram, выполни `/newbot`
   и следуй инструкциям — получишь `TELEGRAM_BOT_TOKEN`.
2. Узнай свой `chat_id`, написав [@userinfobot](https://t.me/userinfobot)
   (или любому подобному боту).
3. Вставь оба значения в `.env` (локально) или в GitHub Secrets (для CI).
4. Напиши своему боту `/start`, чтобы разрешить ему присылать тебе сообщения.

---

## Как настроить GitHub Secrets (для автозапуска через Actions)

В репозитории на GitHub: **Settings → Secrets and variables → Actions**.

### Secrets (обязательно, конфиденциальные значения)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DATABASE_URL` (рекомендуется внешний Postgres, например Neon/Supabase/Railway)

### Secrets / Variables для Gemini (опционально)
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

### Variables (опционально, не секретные, можно не задавать — есть значения по умолчанию)
- `HH_API_BASE_URL`
- `HH_AREA`
- `SCORE_THRESHOLD`

После этого workflow `.github/workflows/job_search.yml` будет:
- запускаться автоматически каждый день в **08:00 UTC**;
- его можно также запустить вручную во вкладке **Actions → Job Search → Run workflow**.

> Рекомендуемый режим для CI/production: внешний Postgres через
> `DATABASE_URL=postgresql+asyncpg://...`. Локально можно оставить SQLite
> через `sqlite+aiosqlite:///data/vacancies.db`.
> Runtime больше не использует `create_all`; актуальная схема БД должна
> применяться через `alembic upgrade head`.

---

## Как работает scoring

Каждая вакансия оценивается от **0 до 100** на основе текста названия,
требований и условий работы:

| Критерий                                   | Баллы  |
|---------------------------------------------|--------|
| Упоминается Python                           | **+20**|
| Упоминается SQL                              | **+15**|
| Упоминается Linux                            | **+15**|
| Упоминается Git                              | **+15**|
| Упоминается Docker                           | **+10**|
| Упоминается FastAPI / Django                 | **+10**|
| Упоминается техподдержка / helpdesk          | **+10**|
| Можно работать удалённо                      | **+10**|
| Требуется опыт от 3 лет                      | **-30**|
| Вакансия уровня Senior / Middle / Lead       | **-50**|

Итоговый score ограничен диапазоном `[0, 100]`. В Telegram отправляются
только вакансии со score **≥ 60** (настраивается через `SCORE_THRESHOLD`).

Каталог навыков, ключевых слов и баллов хранится в
[`job_hunter_bot/skills.py`](job_hunter_bot/skills.py), а используется в
[`job_hunter_bot/scoring.py`](job_hunter_bot/scoring.py),
[`job_hunter_bot/filters.py`](job_hunter_bot/filters.py) и
[`job_hunter_bot/formatting.py`](job_hunter_bot/formatting.py).

Дополнительно:
- совпадения в `title` весят больше, чем совпадения только в `requirements`;
- простые отрицания вроде `SQL не требуется` и `Docker не обязателен` не дают
  положительных баллов;
- формулировки вроде `с 2021 года` больше не считаются признаком `опыт от N лет`;
- если базовый score попадает в диапазон `SEMANTIC_SCORE_MIN..SEMANTIC_SCORE_MAX`
  и задан `GEMINI_API_KEY`, проект запрашивает у Gemini semantic-оценку `0..100`
  и смешивает её с keyword-score по весу `SEMANTIC_SCORE_WEIGHT`.

Профиль кандидата для шаблонного отклика и Gemini-промптов вынесен в
[`job_hunter_bot/candidate_profile.py`](job_hunter_bot/candidate_profile.py).

---

## Как добавить новые поисковые запросы

Есть два способа:

**1. Через `.env` (без изменения кода)**

```env
SEARCH_QUERIES=Junior Python Developer,QA Engineer,DevOps стажер
```

**2. Через код** — добавь строку в список `DEFAULT_SEARCH_QUERIES` в
[`job_hunter_bot/config.py`](job_hunter_bot/config.py):

```python
DEFAULT_SEARCH_QUERIES: list[str] = [
    "Junior Python Developer",
    ...
    "Твой новый запрос",
]
```

Аналогично можно расширить:
- `EXCLUDE_KEYWORDS` в [`job_hunter_bot/config.py`](job_hunter_bot/config.py)
- skill-каталог в [`job_hunter_bot/skills.py`](job_hunter_bot/skills.py)

Это позволит синхронно менять фильтрацию, scoring и блок `Почему подходит`
без дублирования ключевых слов по нескольким файлам.

---

## Команды Telegram-бота

| Команда           | Описание                                              |
|--------------------|--------------------------------------------------------|
| `/start`           | Приветствие и список команд                            |
| `/top [N]`         | Показать топ N вакансий по score (по умолчанию 5)       |
| `/stats`           | Статистика: всего найдено, по статусам, средний score  |
| `/applied <id>`    | Отметить вакансию как «откликнулся»                     |
| `/reject <id>`     | Отклонить вакансию (не будет показываться в `/top`)     |

Инлайн-кнопки под сообщением делают то же самое без ручного ввода ID.

---

## Безопасность

- Реальные токены и ID **никогда** не хранятся в коде или в `.env.example`.
- Файл `.env` добавлен в `.gitignore` и не должен попадать в git.
- В GitHub Actions секреты передаются через `secrets.*`, доступные только во
  время выполнения workflow.

---

## Стек

- Python 3.12
- httpx.AsyncClient — HTTP-клиент для HH API
- SQLAlchemy 2.0 async + SQLite/Postgres — хранение вакансий
- aiogram 3.x — Telegram-бот
- Google Gemini (`google-genai`) — персонализированные черновики откликов
- FastAPI + Jinja2 — веб-дашборд для локальной демонстрации
- Uvicorn — ASGI-сервер для dashboard
- Pydantic Settings — конфигурация через `.env`
- GitHub Actions — расписание и ручной запуск
- pytest / pytest-asyncio — тесты
- Ruff / mypy — линтинг и статический анализ
- Alembic — версионированные миграции схемы БД
- Docker / Docker Compose — упаковка и локальный запуск сервисов

---

## CI

- `.github/workflows/ci.yml` запускает `ruff`, `mypy` и `pytest` на каждый
  `push` в `main` и на каждый `pull_request`.
- `.github/workflows/job_search.yml` запускает ежедневный поиск и больше не
  коммитит локальную SQLite-базу обратно в репозиторий.
- В обоих workflow задан `timeout-minutes: 10`.

---

## Alembic

Первичная миграция уже добавлена в `migrations/versions/`.
Последующие изменения схемы, включая кэш черновиков отклика, тоже
оформляются отдельными миграциями.

Применить миграции:

```bash
alembic upgrade head
```

Создать новую миграцию после изменения моделей:

```bash
alembic revision --autogenerate -m "describe change"
```

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
