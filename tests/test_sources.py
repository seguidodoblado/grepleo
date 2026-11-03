import pytest

from grepleo.models import WorkMode
from grepleo.sources import SOURCES, ApifyError, SearchQuery, plan_search, run_search
from grepleo.sources.base import annual_euros, parse_salary, short_date
from grepleo.sources.indeed import Indeed
from grepleo.sources.infojobs import InfoJobs, province_slug
from grepleo.sources.linkedin import LinkedIn

LONG = "Descripción larga de la oferta. " * 10


def test_parse_salary_handles_spanish_and_english_formats():
    assert parse_salary("30.000 € - 40.000 € Bruto/año") == (30000.0, 40000.0)
    assert parse_salary("€30K/yr - €45K/yr") == (30000.0, 45000.0)
    assert parse_salary("2.000 € brutos/mes") == (24000.0, 24000.0)
    assert parse_salary("15 €/hora") == (27000.0, 27000.0)
    assert parse_salary("45000") == (45000.0, 45000.0)
    assert parse_salary("Salario no disponible") == (None, None) and parse_salary("") == (None, None)
    assert parse_salary("500") == (None, None)       # sin unidad y demasiado pequeño para ser anual o mensual


def test_annual_euros_and_dates():
    assert annual_euros(2000, "MONTH") == 24000 and annual_euros(50000, "YEAR") == 50000
    assert annual_euros(10, "hourly") == 18000 and annual_euros(100, "") == 100
    assert short_date("2026-10-23T10:00:00Z") == "2026-10-23" and short_date(None) == ""


def test_province_slug():
    assert province_slug("Madrid") == "madrid" and province_slug("a Coruña") == "a-coruna"
    assert province_slug("Valencia") == "valencia-valencia" and province_slug("Ciudad Real") == "ciudad-real"
    assert province_slug("Pozuelo") == "" and province_slug("") == ""


def test_infojobs_builds_its_input_and_parses_a_summary_card():
    source = InfoJobs()
    data = source.build_input(SearchQuery("product owner", "Madrid", 30, "week", remote=True))
    assert data == {"query": "product owner", "maxItems": 30, "sortBy": "recent", "sinceDate": "last-7-days",
                    "province": "madrid", "teleworking": ["remote-only"]}
    assert source.build_input(SearchQuery("x", "Pozuelo"))["city"] == "Pozuelo"
    job = source.parse_item({
        "id": "abc", "title": "Product Owner", "author": {"name": "Luca TIC"}, "city": "Madrid",
        "province": {"value": "Madrid"}, "salaryDescription": "40.000 € - 50.000 € Bruto/año",
        "teleworking": {"value": "Solo teletrabajo"}, "contractType": {"value": "Indefinido"},
        "experienceMin": {"value": "Al menos 3 años"}, "study": {"value": "Grado"},
        "requirementMin": "Scrum y Power BI", "link": "https://www.infojobs.net/x", "published": "2026-10-20T08:00"})
    assert job.key == "infojobs:abc" and job.company == "Luca TIC" and job.location == "Madrid, Madrid"
    assert (job.salary_min, job.salary_max) == (40000.0, 50000.0) and job.work_mode is WorkMode.REMOTE
    assert job.experience_text == "Al menos 3 años" and job.studies_text == "Grado"
    assert job.full_description is False and "Scrum" in job.description and job.posted == "2026-10-20"
    assert source.parse_item({"title": "sin id"}) is None


def test_indeed_parses_salary_description_and_closed_flag():
    source = Indeed()
    assert source.build_input(SearchQuery("po", "", 10, "day", remote=True)) == {
        "country": "es", "title": "po", "limit": 10, "location": "remote", "datePosted": "1"}
    job = source.parse_item({
        "key": "k1", "title": "Product Owner de Datos", "employer": {"name": "AGH"}, "location": {"city": "Pozuelo"},
        "description": {"text": LONG + " Trabajo híbrido"}, "baseSalary": {"currencyCode": "EUR", "min": 3000,
                                                                          "max": 4000, "unitOfWork": "MONTH"},
        "jobTypes": {"X": "Tiempo completo"}, "datePublished": "2026-10-22T00:00:00Z", "expired": True,
        "jobUrl": "https://es.indeed.com/viewjob?jk=k1"})
    assert job.key == "indeed:k1" and job.company == "AGH" and job.location == "Pozuelo"
    assert (job.salary_min, job.salary_max) == (36000.0, 48000.0) and job.full_description and job.closed
    assert job.work_mode is WorkMode.HYBRID and job.url.endswith("jk=k1")
    usd = source.parse_item({"key": "k2", "title": "t", "baseSalary": {"currencyCode": "USD", "min": 5, "max": 9,
                                                                       "unitOfWork": "HOUR"}})
    assert usd.salary_min is None and usd.full_description is False


def test_linkedin_builds_and_parses():
    source = LinkedIn()
    assert source.build_input(SearchQuery("po", "", 5, "month")) == {
        "keywords": "po", "location": "España", "limit": 5, "datePosted": "r2592000"}
    job = source.parse_item({"id": "9", "title": "PO", "companyName": "ERNI", "location": "Madrid",
                             "workType": "Remote", "salary": "€60K/yr - €70K/yr", "description": LONG,
                             "url": "https://www.linkedin.com/jobs/view/9", "postedDate": "2026-10-23"})
    assert job.key == "linkedin:9" and job.work_mode is WorkMode.REMOTE and job.salary_max == 70000.0
    assert job.full_description and job.company == "ERNI"


def test_cost_estimate_and_limit_for_budget():
    assert InfoJobs().estimate_cost(100) == pytest.approx(0.101)
    assert Indeed().limit_for_budget(0.0015, 100) == 5 and Indeed().limit_for_budget(0.0, 100) == 1
    assert InfoJobs().limit_for_budget(10, 20) == 20


def test_plan_splits_the_budget_and_trims_each_source():
    runs = plan_search(SearchQuery("po", limit=500), ["infojobs", "indeed", "nope"], 0.2)
    assert [run.source.id for run in runs] == ["infojobs", "indeed"]
    assert all(run.cap_usd == pytest.approx(0.1) for run in runs)
    assert runs[0].limit == 99 and runs[1].limit == 500
    assert all(run.estimate_usd <= run.cap_usd + 1e-9 for run in runs)
    assert plan_search(SearchQuery("po"), [], 1.0) == []
    assert set(SOURCES) == {"infojobs", "indeed", "linkedin"}


def test_run_search_keeps_going_when_one_source_fails():
    calls = []

    def runner(token, actor, actor_input, cap):
        calls.append((token, actor, cap))
        if actor == InfoJobs.actor:
            raise ApifyError("sin crédito")
        return [{"key": "1", "title": "PO", "description": {"text": LONG}}, {"sin": "título"}]

    progress = []
    runs = plan_search(SearchQuery("po", limit=10), ["infojobs", "indeed"], 1.0)
    results = run_search("TOKEN", SearchQuery("po", limit=10), runs, runner, progress.append)
    assert progress == ["InfoJobs", "Indeed"] and len(calls) == 2 and calls[0][0] == "TOKEN"
    assert results[0].error == "sin crédito" and results[0].jobs == []
    assert [job.key for job in results[1].jobs] == ["indeed:1"] and results[1].error == ""
