import asyncio

import httpx
import pytest

from job_hunter_bot import hh_client as hh_client_module
from job_hunter_bot.hh_client import (
    HHClient,
    QuerySearchResult,
    RawVacancy,
    _get_with_retry,
    _parse_item,
)


def make_raw_vacancy(url: str) -> RawVacancy:
    return RawVacancy(
        external_id=url.rsplit("/", 1)[-1],
        title="Junior Python Developer",
        company="Example Inc",
        salary="100000 RUB",
        city="Moscow",
        remote=True,
        url=url,
        requirements="Python SQL Git",
        experience="Нет опыта",
        schedule="Полный день",
    )


def make_response(
    status_code: int,
    payload: dict,
    *,
    url: str = "https://api.hh.ru/vacancies",
) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, json=payload, request=request)


def make_hh_item(**overrides: object) -> dict:
    item = {
        "id": "42",
        "name": "Junior Python Developer",
        "salary": {"from": 100000, "to": 150000, "currency": "RUR"},
        "employer": {"name": "ACME"},
        "area": {"name": "Москва"},
        "alternate_url": "https://hh.ru/vacancy/42",
        "experience": {"name": "Нет опыта"},
        "schedule": {"id": "remote", "name": "Удалённая работа"},
        "snippet": {
            "requirement": "Python, SQL",
            "responsibility": "Поддержка сервиса",
        },
        "key_skills": [{"name": "Git"}, {"name": "Linux"}],
    }
    item.update(overrides)
    return item


class FakeAsyncClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, str | int]]] = []

    async def get(self, url: str, params: dict[str, str | int]) -> httpx.Response:
        self.calls.append((url, params))
        return self._responses.pop(0)


def test_parse_item_formats_salary_and_remote_fields() -> None:
    vacancy = _parse_item(make_hh_item())

    assert vacancy.external_id == "42"
    assert vacancy.salary == "100000–150000 RUR"
    assert vacancy.remote is True
    assert vacancy.company == "ACME"
    assert vacancy.city == "Москва"
    assert vacancy.requirements == "Python, SQL Поддержка сервиса Git, Linux"


def test_parse_item_handles_empty_fields() -> None:
    vacancy = _parse_item(
        make_hh_item(
            name=None,
            salary=None,
            employer=None,
            area=None,
            alternate_url="",
            experience=None,
            schedule={"id": "fullDay", "name": "Полный день"},
            snippet=None,
            key_skills=None,
        )
    )

    assert vacancy.title == "Без названия"
    assert vacancy.salary == "Не указана"
    assert vacancy.company == "Не указана"
    assert vacancy.city == ""
    assert vacancy.remote is False
    assert vacancy.requirements == ""
    assert vacancy.experience == ""


@pytest.mark.asyncio
async def test_get_with_retry_retries_after_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAsyncClient(
        [
            make_response(429, {"errors": []}),
            make_response(200, {"items": [], "pages": 1}),
        ]
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(hh_client_module.random, "uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr(hh_client_module.asyncio, "sleep", fake_sleep)

    response = await _get_with_retry(
        client,
        "https://api.hh.ru/vacancies",
        {"text": "python"},
        semaphore=asyncio.Semaphore(1),
    )

    assert response.status_code == 200
    assert len(client.calls) == 2
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_get_with_retry_raises_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeAsyncClient(
        [
            make_response(429, {"errors": []}),
            make_response(429, {"errors": []}),
            make_response(429, {"errors": []}),
        ]
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(hh_client_module.random, "uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr(hh_client_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(httpx.HTTPStatusError):
        await _get_with_retry(
            client,
            "https://api.hh.ru/vacancies",
            {"text": "python"},
            max_retries=3,
            semaphore=asyncio.Semaphore(1),
        )

    assert len(client.calls) == 3
    assert sleeps == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_search_stops_when_reported_pages_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def fake_get_with_retry(
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, str | int],
        max_retries: int = 3,
        semaphore: asyncio.Semaphore | None = None,
    ) -> httpx.Response:
        del client, url, max_retries, semaphore
        calls.append(int(params["page"]))
        return make_response(200, {"items": [make_hh_item()], "pages": 1})

    monkeypatch.setattr(hh_client_module, "_get_with_retry", fake_get_with_retry)

    client = HHClient()
    try:
        result = await client.search("python", pages=5)
    finally:
        await client.aclose()

    assert calls == [0]
    assert result.attempted_requests == 1
    assert len(result.vacancies) == 1


@pytest.mark.asyncio
async def test_search_stops_when_items_become_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        make_response(
            200,
            {
                "items": [make_hh_item(id="1", alternate_url="https://hh.ru/vacancy/1")],
                "pages": 5,
            },
        ),
        make_response(200, {"items": [], "pages": 5}),
    ]

    async def fake_get_with_retry(
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, str | int],
        max_retries: int = 3,
        semaphore: asyncio.Semaphore | None = None,
    ) -> httpx.Response:
        del client, url, params, max_retries, semaphore
        return responses.pop(0)

    monkeypatch.setattr(hh_client_module, "_get_with_retry", fake_get_with_retry)

    client = HHClient()
    try:
        result = await client.search("python", pages=5)
    finally:
        await client.aclose()

    assert result.attempted_requests == 2
    assert [vacancy.external_id for vacancy in result.vacancies] == ["1"]


@pytest.mark.asyncio
async def test_search_many_collects_failed_query_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(self, query: str, pages: int | None = None) -> QuerySearchResult:
        del pages
        if query == "bad":
            return QuerySearchResult(
                query=query,
                vacancies=[],
                failed_requests=1,
                attempted_requests=1,
            )
        return QuerySearchResult(
            query=query,
            vacancies=[make_raw_vacancy(f"https://hh.ru/vacancy/{query}")],
            failed_requests=0,
            attempted_requests=1,
        )

    monkeypatch.setattr(HHClient, "search", fake_search)

    client = HHClient()
    try:
        result = await client.search_many(["good", "bad"])
    finally:
        await client.aclose()

    assert len(result.vacancies) == 1
    assert result.failed_queries == {"bad": 1}
    assert result.failed_requests == 1
    assert result.attempted_requests == 2
    assert result.failure_ratio == 0.5
