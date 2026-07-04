from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from job_hunter_bot.web import app as web_app_module


def make_vacancy() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        external_id="hh-7",
        title="Junior Python Developer",
        company="Example Inc",
        salary="100000 RUB",
        city="Moscow",
        remote=True,
        url="https://example.com/vacancy/7",
        requirements="Python SQL Git Linux FastAPI support",
        source="hh.ru",
        status="new",
        score=88,
    )


def test_dashboard_renders_vacancy_and_stats(monkeypatch) -> None:
    async def fake_init_db():
        return None

    async def fake_load_dashboard_data():
        return (
            [make_vacancy()],
            {
                "total": 1,
                "new": 1,
                "viewed": 0,
                "applied": 0,
                "rejected": 0,
                "avg_score": 88.0,
                "remote": 1,
                "high_score": 1,
            },
        )

    monkeypatch.setattr(web_app_module, "init_db", fake_init_db)
    monkeypatch.setattr(web_app_module, "load_dashboard_data", fake_load_dashboard_data)

    with TestClient(web_app_module.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "job_hunter_bot dashboard" in response.text
    assert "Junior Python Developer" in response.text
    assert "Example Inc" in response.text
    assert "Score 88/100" in response.text
