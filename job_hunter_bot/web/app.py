"""FastAPI dashboard for browsing saved vacancies and summary stats."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from job_hunter_bot.crud import get_stats, get_top
from job_hunter_bot.db import get_session, init_db

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="job_hunter_bot dashboard",
    description="Visual dashboard for saved vacancies and search stats.",
    lifespan=lifespan,
)


async def load_dashboard_data() -> tuple[list[Any], dict[str, int | float]]:
    session = get_session()
    try:
        vacancies = await get_top(session, limit=50)
        stats = await get_stats(session)
        return vacancies, stats
    finally:
        await session.close()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    vacancies, stats = await load_dashboard_data()
    context = {
        "request": request,
        "vacancies": vacancies,
        "stats": stats,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
