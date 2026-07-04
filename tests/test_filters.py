from job_hunter_bot.config import settings
from job_hunter_bot.filters import filter_vacancies, is_relevant
from job_hunter_bot.hh_client import RawVacancy


def make_vacancy(**overrides) -> RawVacancy:
    defaults = dict(
        external_id="1",
        title="Junior Python Developer",
        company="ACME",
        salary="Не указана",
        city="Москва",
        remote=False,
        url="https://hh.ru/vacancy/1",
        requirements="Python, SQL, Git",
        experience="Нет опыта",
        schedule="Полный день",
    )
    defaults.update(overrides)
    return RawVacancy(**defaults)


def test_junior_vacancy_is_relevant():
    v = make_vacancy()
    assert is_relevant(v) is True


def test_senior_vacancy_excluded():
    v = make_vacancy(title="Senior Python Developer", experience="От 3 до 6 лет")
    assert is_relevant(v) is False


def test_lead_vacancy_excluded():
    v = make_vacancy(title="Team Lead Python", experience="Нет опыта")
    assert is_relevant(v) is False


def test_experience_3plus_excluded():
    v = make_vacancy(
        title="Python Developer",
        requirements="Требуется опыт разработки от 3 лет",
        experience="От 1 года до 3 лет",
    )
    assert is_relevant(v) is False


def test_helpdesk_included():
    v = make_vacancy(
        title="Специалист Helpdesk",
        requirements="Работа с обращениями пользователей, техническая поддержка",
        experience="Нет опыта",
    )
    assert is_relevant(v) is True


def test_irrelevant_vacancy_without_junior_keywords_excluded():
    v = make_vacancy(
        title="Менеджер по продажам",
        requirements="Продажи, переговоры",
        experience="От 1 года до 3 лет",
    )
    assert is_relevant(v) is False


def test_filter_vacancies_list():
    good = make_vacancy()
    bad = make_vacancy(title="Senior Backend Developer", experience="От 3 до 6 лет", url="https://hh.ru/vacancy/2")
    result = filter_vacancies([good, bad])
    assert result == [good]


def test_max_experience_years_setting_affects_filter(monkeypatch):
    vacancy = make_vacancy(
        title="Junior Support Specialist",
        requirements="Helpdesk, поддержка пользователей",
        experience="От 3 до 6 лет",
    )

    monkeypatch.setattr(settings, "max_experience_years", 3)
    assert is_relevant(vacancy) is False

    monkeypatch.setattr(settings, "max_experience_years", 4)
    assert is_relevant(vacancy) is True


def test_experience_regex_does_not_match_calendar_years() -> None:
    vacancy = make_vacancy(
        title="Junior Python Developer",
        requirements="Поддержка продукта с 2021 года, Python, SQL",
        experience="От 1 года до 3 лет",
    )
    assert is_relevant(vacancy) is True


def test_negated_include_keyword_does_not_make_vacancy_relevant() -> None:
    vacancy = make_vacancy(
        title="Оператор чата",
        requirements="Helpdesk не требуется, опыт в продажах приветствуется",
        experience="От 1 года до 3 лет",
    )
    assert is_relevant(vacancy) is False
