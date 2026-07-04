import pytest

from job_hunter_bot import llm


class DummyVacancy:
    title = "Junior Python Developer"
    company = "Example Inc"
    requirements = "Python SQL Git Linux"


@pytest.mark.asyncio
async def test_generate_draft_reply_falls_back_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm.settings, "gemini_api_key", "")

    draft = await llm.generate_draft_reply(DummyVacancy())

    assert "Меня заинтересовала вакансия" in draft


@pytest.mark.asyncio
async def test_generate_draft_reply_falls_back_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs):
            return None

    class FakeAioClient:
        models = FakeModels()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.aio = FakeAioClient()

    async def fake_wait_for(coro, timeout):
        coro.close()
        raise TimeoutError

    monkeypatch.setattr(llm.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(llm.genai, "Client", FakeClient)
    monkeypatch.setattr(llm.asyncio, "wait_for", fake_wait_for)

    draft = await llm.generate_draft_reply(DummyVacancy())

    assert "Меня заинтересовала вакансия" in draft


def test_extract_score_reads_numeric_response() -> None:
    assert llm._extract_score("72") == 72
    assert llm._extract_score("score: 101") is None


def test_blend_scores_uses_configured_weight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm.settings, "semantic_score_weight", 0.4)
    assert llm.blend_scores(50, 80) == 62


@pytest.mark.asyncio
async def test_generate_semantic_score_falls_back_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm.settings, "gemini_api_key", "")

    score = await llm.generate_semantic_score(DummyVacancy())

    assert score is None
