from job_hunter_bot.bot import vacancy_keyboard


def test_vacancy_keyboard_contains_actions() -> None:
    keyboard = vacancy_keyboard(42)

    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 2
    assert keyboard.inline_keyboard[0][0].callback_data == "applied:42"
    assert keyboard.inline_keyboard[0][1].callback_data == "reject:42"
