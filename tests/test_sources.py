import pytest

from grepleo.models import WorkMode
from grepleo.sources import SOURCES, ApifyError, SearchQuery, plan_search, run_search
from grepleo.sources.base import annual_euros, parse_salary, short_date
from grepleo.sources.indeed import Indeed
from grepleo.sources.infojobs import InfoJobs
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


INFOJOBS_ITEM = {
    "id": "c7f8f42da94975b10ff7414c2990d5", "url": "https://www.infojobs.net/madrid/administrador/of-ic7f8f42d",
    "title": "Administrador/a Directorio activo Hibrido Madrid", "company": "CAS Training", "city": "Madrid",
    "workMode": "Hybrid", "contractType": "Contrato indefinido", "salaryRaw": "28.000 – 36.000 € / YEAR",
    "salaryMin": 28000, "salaryMax": 36000, "salaryCurrency": "EUR", "salaryPeriod": "YEAR",
    "publishDateISO": "2026-11-04", "descriptionText": "Funciones\n" + "Experiencia con PowerShell y Azure AD. " * 8}


def test_infojobs_asks_for_full_details_and_parses_a_complete_offer():
    source = InfoJobs()
    assert source.actor == "unfenced-group/infojobs-net-scraper"
    assert source.build_input(SearchQuery("aws, devops", "Madrid", 30, "week")) == {
        "searchQuery": "aws, devops", "maxItems": 30, "fetchDetails": True, "location": "Madrid", "daysOld": 7}
    assert source.build_input(SearchQuery("x", "", 5, "month"))["daysOld"] == 30
    assert "location" not in source.build_input(SearchQuery("x")) and "daysOld" not in source.build_input(SearchQuery("x"))
    job = source.parse_item(INFOJOBS_ITEM)
    assert job.key == "infojobs:c7f8f42da94975b10ff7414c2990d5" and job.company == "CAS Training"
    assert job.location == "Madrid" and job.work_mode is WorkMode.HYBRID and job.contract == "Contrato indefinido"
    assert (job.salary_min, job.salary_max) == (28000.0, 36000.0) and job.salary_text == "28.000–36.000 €"
    assert job.full_description and "PowerShell" in job.description and job.posted == "2026-11-04"
    assert job.url.endswith("of-ic7f8f42d")
    assert source.parse_item({"title": "sin id"}) is None and source.parse_item({"id": "1"}) is None


def test_infojobs_handles_monthly_pay_missing_pay_and_unknown_work_modes():
    source = InfoJobs()
    monthly = source.parse_item({**INFOJOBS_ITEM, "salaryMin": 2000, "salaryMax": None, "salaryPeriod": "MONTH"})
    assert (monthly.salary_min, monthly.salary_max) == (24000.0, 24000.0)
    unpaid = source.parse_item({**INFOJOBS_ITEM, "salaryMin": None, "salaryMax": None, "salaryRaw": None})
    assert unpaid.salary_min is None and unpaid.salary_text == ""
    dollars = source.parse_item({**INFOJOBS_ITEM, "salaryCurrency": "USD"})
    assert dollars.salary_min is None
    assert source.parse_item({**INFOJOBS_ITEM, "workMode": "On-site"}).work_mode is WorkMode.ONSITE
    assert source.parse_item({**INFOJOBS_ITEM, "workMode": "Remote"}).work_mode is WorkMode.REMOTE
    guessed = source.parse_item({**INFOJOBS_ITEM, "workMode": None, "title": "DevOps 100% remoto"})
    assert guessed.work_mode is WorkMode.REMOTE                     # sin dato del portal, se deduce del texto
    short = source.parse_item({**INFOJOBS_ITEM, "descriptionText": "Scrum"})
    assert short.full_description is False


def test_infojobs_keeps_only_remote_offers_when_asked_because_its_actor_cannot_filter():
    source = InfoJobs()
    jobs = [source.parse_item({**INFOJOBS_ITEM, "id": "1", "workMode": "Remote"}),
            source.parse_item({**INFOJOBS_ITEM, "id": "2", "workMode": "Hybrid"}),
            source.parse_item({**INFOJOBS_ITEM, "id": "3", "workMode": "On-site"})]
    assert [job.key for job in source.refine(jobs, SearchQuery("x", remote=True))] == ["infojobs:1"]
    assert source.refine(jobs, SearchQuery("x")) == jobs
    runs = plan_search(SearchQuery("x", limit=5, remote=True), ["infojobs"], 1.0)
    items = [{**INFOJOBS_ITEM, "id": str(n), "workMode": mode} for n, mode in enumerate(("Remote", "Hybrid"))]
    results = run_search("T", SearchQuery("x", limit=5, remote=True), runs, runner=lambda *args: items)
    assert [job.key for job in results[0].jobs] == ["infojobs:0"]


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
    assert InfoJobs().estimate_cost(100) == pytest.approx(0.00005 + 0.079)
    assert Indeed().limit_for_budget(0.0015, 100) == 5 and Indeed().limit_for_budget(0.0, 100) == 1
    assert InfoJobs().limit_for_budget(10, 20) == 20


def test_plan_splits_the_budget_and_trims_each_source():
    runs = plan_search(SearchQuery("po", limit=500), ["infojobs", "indeed", "nope"], 0.2)
    assert [run.source.id for run in runs] == ["infojobs", "indeed"]
    assert all(run.cap_usd == pytest.approx(0.1) for run in runs)
    assert runs[0].limit == 126 and runs[1].limit == 500
    assert all(run.estimate_usd <= run.cap_usd + 1e-9 for run in runs)
    assert plan_search(SearchQuery("po"), [], 1.0) == []
    assert set(SOURCES) == {"infojobs", "indeed", "linkedin", "tecnoempleo", "michaelpage"}
    tecno = plan_search(SearchQuery("po", limit=500), ["tecnoempleo"], 0.25)[0]
    assert tecno.limit == 160 and tecno.estimate_usd <= 0.25 + 1e-9   # 0,01 $ de arranque + 0,0015 $ por oferta


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


def test_tecnoempleo_builds_and_parses():
    from grepleo.sources.tecnoempleo import Tecnoempleo
    source = Tecnoempleo()
    base = {"query": "po", "maxResults": 5, "includeDetails": True, "descriptionFormat": "text",
            "excludeEmptyFields": True}
    assert source.build_input(SearchQuery("po", "Madrid", 5)) == {**base, "province": "Madrid"}
    remote = source.build_input(SearchQuery("po", "Madrid", 5, remote=True))
    assert remote["en_remoto"] == "1" and "province" not in remote        # remoto: sin provincia
    assert "date_start" in source.build_input(SearchQuery("po", "", 5, "week"))
    job = source.parse_item({
        "jobId": "j1", "title": "Data Engineer", "company": "Baoss", "location": "Madrid",
        "province": "Madrid (Híbrido)", "workArrangement": "HYBRID", "salaryMin": 36000, "salaryMax": 48000,
        "salaryCurrency": "EUR", "salaryPeriod": "YEAR", "salaryText": "€36000–€48000/year",
        "contractType": "Indefinido", "experienceLevel": "3-5 años", "educationLevel": "FP2/Grado Superior",
        "technologies": ["snowflake", "dbt."], "descriptionText": LONG, "detailFetched": True,
        "publishDateISO": "2026-11-04T00:00:00.000Z", "url": "https://www.tecnoempleo.com/x"})
    assert job.key == "tecnoempleo:j1" and job.company == "Baoss" and job.work_mode is WorkMode.HYBRID
    assert (job.salary_min, job.salary_max) == (36000.0, 48000.0) and job.full_description
    assert job.experience_text == "3-5 años" and job.posted == "2026-11-04"
    assert job.salary_text == "36.000–48.000 €"
    assert "Tecnologías: snowflake, dbt" in job.description
    remote_job = source.parse_item({"jobId": "j2", "title": "AWS DevOps", "location": "100% remoto",
                                    "province": "100% remoto", "workArrangement": None})
    assert remote_job.work_mode is WorkMode.REMOTE and remote_job.full_description is False
    dollars = source.parse_item({"jobId": "j3", "title": "t", "salaryMin": 5, "salaryCurrency": "USD"})
    assert dollars.salary_min is None
    assert source.parse_item({"title": "sin id"}) is None


TILE = ('<li class="views-row"><div class="job-tile"><div class="job-title"><h3><a href="/job-detail/{slug}/ref/{ref}" '
        'rel="bookmark">{title}</a></h3><div class="job-logo"><a href=/clientprofile/x><img alt="Elian Logo"></a></div></div>'
        '<div class="job-properties"><div class="job-location"><i class="fal"></i> {place}</div>'
        '<div class="job-contract-type"><i class="far"></i> Permanente</div></div>'
        '<div class="job-summary"><div class="job_advert__job-summary-text"><p>Resumen de <strong>{title}</strong></p></div></div>'
        '</div></li>')
DETAIL = ('<script type="application/ld+json">{{"@type": "JobPosting", "datePosted": "{posted}", "industry": "Tecnolog\u00eda", '
          '"description": "<p>Trabajo <strong>h\u00edbrido</strong>.</p><ul><li>Terraform</li><li>Kubernetes</li></ul>{relleno}", '
          '"jobLocationType": "TELECOMMUTE", "jobLocation": {{"address": {{"addressLocality": "Madrid"}}}}}}</script>'
          '<script>dataLayer = {{"contract":"permanent","salary":{salary},"salaryCurrency":"EUR"}}</script>')


def _today():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date()


def listing(*jobs):
    return "<ul>" + "".join(TILE.format(slug=f"puesto-{n}", ref=f"jn-{n}", title=title, place=place)
                            for n, (title, place) in enumerate(jobs)) + "</ul>"


class FakeResponse:
    def __init__(self, body):
        self.body = body.encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_web(pages, details):
    """Un `opener` que sirve las páginas de resultados por su número y las fichas por su enlace."""
    calls = []

    def opener(request, timeout):
        url = request.full_url
        calls.append((url, request.get_header("User-agent")))
        if "/job-detail/" in url:
            return FakeResponse(details[url])
        page = int(url.rsplit("page=", 1)[-1])
        return FakeResponse(pages[page])
    return opener, calls


def test_michaelpage_reads_listing_and_detail_without_apify():
    from grepleo.sources.michaelpage import MichaelPage
    today = _today().isoformat()
    long_text = "x" * 200
    pages = [listing(("DevOps Engineer", "Madrid"), ("SRE", "Barcelona Ciudad"), ("Cloud", "100% Remoto"))]
    base = "https://www.michaelpage.es"
    details = {f"{base}/job-detail/puesto-{n}/ref/jn-{n}": DETAIL.format(posted=today, salary=60000, relleno=long_text)
               for n in range(3)}
    opener, calls = fake_web(pages, details)
    source = MichaelPage(opener=opener, pause=0)
    assert source.local and source.estimate_cost(100) == 0
    items = source.fetch(SearchQuery("devops", "Madrid", 10))
    assert [item["title"] for item in items] == ["DevOps Engineer", "Cloud"]      # Barcelona se descarta; el remoto no
    assert all("Grepleo/" in agent for _url, agent in calls)                      # se identifica con su nombre
    assert "search=devops" in calls[0][0] and "page=0" in calls[0][0]
    job = source.parse_item(items[0])
    assert job.key == "michaelpage:jn-0" and job.company == "Elian" and job.location == "Madrid"
    assert job.full_description and "- Terraform" in job.description and job.work_mode is WorkMode.HYBRID
    assert job.salary_text == "desde 60.000 €" and job.salary_min is None and job.salary_max is None
    assert job.contract == "Permanente" and job.posted == today and job.url.endswith("/ref/jn-0")


def test_michaelpage_pages_dedupes_and_applies_the_date_window():
    from datetime import timedelta

    from grepleo.sources.michaelpage import PAGE_SIZE, MichaelPage
    old = (_today() - timedelta(days=40)).isoformat()
    first = listing(*[(f"Puesto {n}", "Madrid") for n in range(PAGE_SIZE)])
    second = listing(("Puesto 0", "Madrid"), ("Antiguo", "Madrid"))     # el primero ya estaba en la página anterior
    base = "https://www.michaelpage.es/job-detail"
    details = {f"{base}/puesto-{n}/ref/jn-{n}": DETAIL.format(posted=_today().isoformat(), salary=0, relleno="")
               for n in range(PAGE_SIZE)}
    details[f"{base}/puesto-1/ref/jn-1"] = DETAIL.format(posted=old, salary=0, relleno="")
    opener, _calls = fake_web([first, second], details)
    source = MichaelPage(opener=opener, pause=0)
    items = source.fetch(SearchQuery("x", limit=PAGE_SIZE + 5, posted="month"))
    assert len(items) == PAGE_SIZE - 1 and all(item["title"] != "Puesto 1" for item in items)   # la de hace 40 días sobra
    assert source.parse_item({**items[0], "salary": 0}).salary_text == ""


def test_michaelpage_keeps_the_summary_when_a_detail_page_fails():
    from grepleo.sources.michaelpage import MichaelPage
    page = listing(("DevOps", "Madrid"))

    def opener(request, timeout):
        if "/job-detail/" in request.full_url:
            raise OSError("sin red")
        return FakeResponse(page)
    items = MichaelPage(opener=opener, pause=0).fetch(SearchQuery("devops", limit=5))
    job = MichaelPage().parse_item(items[0])
    assert job.full_description is False and "Resumen" in job.description


def test_michaelpage_reports_a_failing_listing_and_parse_item_needs_a_title():
    import urllib.error

    from grepleo.sources import SourceError
    from grepleo.sources.michaelpage import MichaelPage

    def blocked(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "no", {}, None)
    with pytest.raises(SourceError, match="403"):
        MichaelPage(opener=blocked, pause=0).fetch(SearchQuery("devops"))
    assert MichaelPage().parse_item({"url": "https://www.michaelpage.es/x"}) is None


def test_local_sources_cost_nothing_and_need_no_token():
    runs = plan_search(SearchQuery("po", limit=30), ["michaelpage", "tecnoempleo"], 0.5)
    local, paid = runs
    assert local.cap_usd == 0 and local.estimate_usd == 0 and local.limit == 30
    assert paid.cap_usd == pytest.approx(0.5)                            # el presupuesto solo se reparte entre las de Apify
    assert plan_search(SearchQuery("po"), ["michaelpage"], 0.0)[0].estimate_usd == 0

    class Offline:
        id, name, local, actor = "x", "Local", True, ""
        estimate_cost = lambda self, limit: 0.0
        limit_for_budget = lambda self, budget, wanted: wanted

        def fetch(self, query):
            return [{"title": "PO", "url": "https://x/ref/1"}]

        def refine(self, jobs, query):
            return jobs

        def parse_item(self, item):
            return MichaelPage_job(item)

    def MichaelPage_job(item):
        from grepleo.models import Job
        return Job(key="x:1", source="x", title=item["title"])

    runs = plan_search(SearchQuery("po"), ["infojobs"], 0.1)
    runs[0].source = Offline()
    results = run_search("", SearchQuery("po"), runs, runner=lambda *a: pytest.fail("no debe llamar a Apify"))
    assert [job.key for job in results[0].jobs] == ["x:1"]


def test_michaelpage_treats_404_as_no_results_and_searches_each_comma_term():
    import urllib.error

    from grepleo.sources.michaelpage import MichaelPage
    seen = []

    def opener(request, timeout):
        url = request.full_url
        if "/job-detail/" in url:
            return FakeResponse(DETAIL.format(posted=_today().isoformat(), salary=0, relleno=""))
        seen.append(url)
        if "search=aws" in url:
            return FakeResponse(listing(("AWS Engineer", "Madrid")))
        raise urllib.error.HTTPError(url, 404, "sin ofertas", {}, None)
    items = MichaelPage(opener=opener, pause=0).fetch(SearchQuery("aws, devops junior", limit=5))
    assert [item["title"] for item in items] == ["AWS Engineer"]
    assert any("search=devops+junior" in url for url in seen) and any("search=aws&" in url for url in seen)
    assert MichaelPage(opener=opener, pause=0).fetch(SearchQuery("nada", limit=5)) == []
