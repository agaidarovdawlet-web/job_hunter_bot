"""Клиент для получения вакансий через публичный API hh.ru."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field

import httpx

from job_hunter_bot.config import settings

logger = logging.getLogger(__name__)


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str | int],
    max_retries: int = 3,
    semaphore: asyncio.Semaphore | None = None,
) -> httpx.Response:
    response: httpx.Response | None = None
    for attempt in range(max_retries):
        if semaphore is None:
            response = await client.get(url, params=params)
        else:
            async with semaphore:
                response = await client.get(url, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            return response

        wait = (2**attempt) + random.uniform(0, 1)
        logger.warning("HH API rate limited, retry in %.1fs", wait)
        await asyncio.sleep(wait)

    assert response is not None
    response.raise_for_status()
    return response


@dataclass
class RawVacancy:
    """Сырые данные вакансии, полученные из HH API, в удобном виде."""

    external_id: str
    title: str
    company: str
    salary: str
    city: str
    remote: bool
    url: str
    requirements: str
    experience: str
    schedule: str
    source: str = "hh.ru"
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class QuerySearchResult:
    query: str
    vacancies: list[RawVacancy]
    failed_requests: int = 0
    attempted_requests: int = 0


@dataclass
class SearchManyResult:
    vacancies: list[RawVacancy]
    failed_queries: dict[str, int]
    failed_requests: int
    attempted_requests: int

    @property
    def failure_ratio(self) -> float:
        if self.attempted_requests == 0:
            return 0.0
        return self.failed_requests / self.attempted_requests


def _format_salary(salary: dict | None) -> str:
    if not salary:
        return "Не указана"
    lo, hi, cur = salary.get("from"), salary.get("to"), salary.get("currency", "")
    if lo and hi:
        return f"{lo}–{hi} {cur}"
    if lo:
        return f"от {lo} {cur}"
    if hi:
        return f"до {hi} {cur}"
    return "Не указана"


def _is_remote(item: dict) -> bool:
    schedule = (item.get("schedule") or {}).get("id", "")
    name = (item.get("schedule") or {}).get("name", "").lower()
    return schedule == "remote" or "удал" in name


def _parse_item(item: dict) -> RawVacancy:
    snippet = item.get("snippet") or {}
    requirement = (snippet.get("requirement") or "") or ""
    responsibility = (snippet.get("responsibility") or "") or ""
    key_skills = ", ".join(s.get("name", "") for s in item.get("key_skills", []) or [])
    requirements_text = " ".join(
        part for part in (requirement, responsibility, key_skills) if part
    ).strip()

    employer = item.get("employer") or {}
    area = item.get("area") or {}
    experience = (item.get("experience") or {}).get("name", "")
    schedule = (item.get("schedule") or {}).get("name", "")

    return RawVacancy(
        external_id=str(item.get("id")),
        title=item.get("name") or "Без названия",
        company=employer.get("name", "Не указана"),
        salary=_format_salary(item.get("salary")),
        city=area.get("name", ""),
        remote=_is_remote(item),
        url=item.get("alternate_url") or "",
        requirements=requirements_text,
        experience=experience,
        schedule=schedule,
        raw=item,
    )


class HHClient:
    """Тонкая обёртка над https://api.hh.ru/vacancies."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        self.base_url = base_url or settings.hh_api_base_url
        self._request_semaphore = asyncio.Semaphore(settings.hh_max_concurrent_requests)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": settings.hh_user_agent},
            trust_env=False,
        )

    async def search(self, query: str, pages: int | None = None) -> QuerySearchResult:
        """Ищет вакансии по одному текстовому запросу, может пройти несколько страниц."""
        pages = pages or settings.hh_pages_per_query
        results: list[RawVacancy] = []
        failed_requests = 0
        attempted_requests = 0

        for page in range(pages):
            attempted_requests += 1
            try:
                resp = await _get_with_retry(
                    self._client,
                    self.base_url,
                    {
                        "text": query,
                        "area": settings.hh_area,
                        "per_page": settings.hh_per_page,
                        "page": page,
                    },
                    semaphore=self._request_semaphore,
                )
            except httpx.HTTPError as exc:
                failed_requests += 1
                logger.warning("HH API error for query=%r page=%s: %s", query, page, exc)
                break

            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            results.extend(_parse_item(item) for item in items)

            if page + 1 >= data.get("pages", 1):
                break

        return QuerySearchResult(
            query=query,
            vacancies=results,
            failed_requests=failed_requests,
            attempted_requests=attempted_requests,
        )

    async def search_many(self, queries: list[str]) -> SearchManyResult:
        """Ищет по нескольким запросам и объединяет результаты."""
        tasks = []
        for q in queries:
            logger.info("Searching HH for query: %s", q)
            tasks.append(self.search(q))
        results = await asyncio.gather(*tasks)
        failed_queries = {
            result.query: result.failed_requests
            for result in results
            if result.failed_requests > 0
        }
        return SearchManyResult(
            vacancies=[vacancy for result in results for vacancy in result.vacancies],
            failed_queries=failed_queries,
            failed_requests=sum(result.failed_requests for result in results),
            attempted_requests=sum(result.attempted_requests for result in results),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HHClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
