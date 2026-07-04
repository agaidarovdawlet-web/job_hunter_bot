from job_hunter_bot.hh_client import RawVacancy
from job_hunter_bot.scoring import calculate_score


def make_vacancy(**overrides) -> RawVacancy:
    defaults = dict(
        external_id="1",
        title="Junior Python Developer",
        company="ACME",
        salary="100000-150000 RUR",
        city="Москва",
        remote=True,
        url="https://hh.ru/vacancy/1",
        requirements="Python, SQL, Git, Linux, Docker, FastAPI",
        experience="Нет опыта",
        schedule="Удалённая работа",
    )
    defaults.update(overrides)
    return RawVacancy(**defaults)


def test_full_match_scores_high():
    v = make_vacancy()
    score = calculate_score(v)
    # Full keyword match plus title bonus for Python, capped at 100.
    assert score == 100


def test_senior_penalty_applied():
    v = make_vacancy(title="Senior Python Developer")
    score = calculate_score(v)
    assert score <= 50


def test_experience_3plus_penalty():
    v = make_vacancy(requirements="Требуется опыт коммерческой разработки от 3 лет, Python, SQL")
    score = calculate_score(v)
    assert score <= 65  # penalty of -30 applied


def test_score_never_negative():
    v = make_vacancy(
        title="Senior Lead Developer",
        requirements="Опыт от 5 лет",
        remote=False,
    )
    score = calculate_score(v)
    assert score == 0


def test_min_relevant_vacancy():
    v = make_vacancy(
        title="Специалист технической поддержки",
        requirements="Windows, работа с пользователями",
        remote=False,
    )
    score = calculate_score(v)
    assert score == 12


def test_title_match_weighs_more_than_requirement_match():
    title_match = make_vacancy(
        title="Python Developer",
        requirements="Коммуникация с командой",
        remote=False,
    )
    requirements_match = make_vacancy(
        title="Junior Developer",
        requirements="Python, коммуникация с командой",
        remote=False,
    )

    assert calculate_score(title_match) > calculate_score(requirements_match)


def test_negated_keyword_does_not_add_score():
    v = make_vacancy(
        title="Junior Developer",
        requirements="SQL не требуется, Docker не обязателен",
        remote=False,
    )

    assert calculate_score(v) == 0
