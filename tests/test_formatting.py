from types import SimpleNamespace

from job_hunter_bot.formatting import draft_reply, format_telegram_message


def make_vacancy() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        title="Junior Python Developer",
        company="Example Inc",
        salary="100000 RUB",
        city="Moscow",
        remote=True,
        url="https://example.com/vacancy/1",
        requirements="Python SQL Git Linux",
        score=85,
    )


def test_format_telegram_message_uses_custom_draft() -> None:
    vacancy = make_vacancy()
    message = format_telegram_message(vacancy, draft_text="Custom draft")

    assert "Custom draft" in message


def test_format_telegram_message_falls_back_to_template() -> None:
    vacancy = make_vacancy()
    message = format_telegram_message(vacancy)

    assert draft_reply(vacancy) in message
