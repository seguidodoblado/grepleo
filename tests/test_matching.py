from grepleo.matching import categorize, evaluate, fit_from
from grepleo.models import CriterionResult, Fit, Job, Status, WorkMode
from grepleo.profiles import Category, Profile

DESCRIPTION = ("Product Owner de datos. Trabajarás con Scrum y Jira, Power BI y SQL. Se pide inglés C1 y "
               "5-10 años de experiencia. Remoto 100%. " * 2)


def job(**changes) -> Job:
    base = {"key": "indeed:1", "source": "indeed", "title": "Product Owner Data", "company": "ACME",
            "location": "Madrid", "description": DESCRIPTION, "full_description": True}
    base.update(changes)
    return Job(**base)


def profile(**changes) -> Profile:
    base = {"name": "PO", "years": 8, "must": ["Scrum", "Power BI|powerbi"], "nice": ["Snowflake", "SQL"],
            "languages": {"Inglés": "C1"}}
    base.update(changes)
    return Profile(**base)


def by_name(evaluation, name):
    return next(item for item in evaluation.criteria if item.name == name)


def test_skills_found_missing_and_unknown_on_a_summary_card():
    result = evaluate(job(), profile())
    assert by_name(result, "Scrum").status is Status.MET and by_name(result, "Scrum").required
    assert by_name(result, "Power BI").status is Status.MET
    assert by_name(result, "SQL").status is Status.MET
    assert by_name(result, "Snowflake").status is Status.MISSING and not by_name(result, "Snowflake").required
    summary = evaluate(job(description="Scrum", full_description=False), profile())
    assert by_name(summary, "Scrum").status is Status.MET
    assert by_name(summary, "Snowflake").status is Status.UNKNOWN   # una ficha resumida no prueba que falte


def test_experience_and_languages_are_compared_with_the_profile():
    assert by_name(evaluate(job(), profile(years=8)), "Experiencia").status is Status.MET
    low = by_name(evaluate(job(), profile(years=3)), "Experiencia")
    assert low.status is Status.MISSING and "5 años" in low.detail and "3 años" in low.detail
    assert by_name(evaluate(job(), profile()), "Inglés C1").status is Status.MET
    assert by_name(evaluate(job(), profile(languages={"Inglés": "B2"})), "Inglés C1").status is Status.MISSING
    assert by_name(evaluate(job(), profile(languages={})), "Inglés C1").status is Status.MISSING


def test_salary_work_mode_location_and_studies_only_count_when_the_profile_asks_for_them():
    plain = evaluate(job(), profile())
    assert {"Salario", "Modalidad", "Ubicación", "Estudios"}.isdisjoint(c.name for c in plain.criteria)
    asking = profile(salary_min=40000, work_modes=["remote"], locations=["Madrid"], studies="degree")
    unknown = evaluate(job(), asking)
    assert by_name(unknown, "Salario").status is Status.UNKNOWN
    assert by_name(unknown, "Modalidad").status is Status.UNKNOWN
    assert by_name(unknown, "Ubicación").status is Status.MET
    assert by_name(unknown, "Estudios").status is Status.UNKNOWN
    rich = evaluate(job(salary_max=45000.0, work_mode=WorkMode.REMOTE, studies_text="Grado"), asking)
    assert by_name(rich, "Salario").status is Status.MET and by_name(rich, "Modalidad").status is Status.MET
    assert by_name(rich, "Estudios").status is Status.MET
    poor = evaluate(job(salary_max=30000.0, salary_estimated=True, work_mode=WorkMode.ONSITE,
                        location="Valencia", studies_text="Máster"), asking)
    assert by_name(poor, "Salario").status is Status.MISSING and "estimado" in by_name(poor, "Salario").detail
    assert by_name(poor, "Modalidad").status is Status.MISSING
    assert by_name(poor, "Ubicación").status is Status.MISSING
    assert by_name(poor, "Estudios").status is Status.MISSING


def test_remote_jobs_satisfy_any_location():
    result = evaluate(job(work_mode=WorkMode.REMOTE, location="Cádiz"), profile(locations=["Madrid"]))
    assert by_name(result, "Ubicación").status is Status.MET


def test_things_to_avoid_count_against_the_job_when_they_appear():
    found = evaluate(job(description=DESCRIPTION + " Guardias de fin de semana"), profile(avoid=["guardias"]))
    assert by_name(found, "Sin «guardias»").status is Status.MISSING
    clean = evaluate(job(), profile(avoid=["guardias"]))
    assert by_name(clean, "Sin «guardias»").status is Status.MET


def test_fit_levels():
    met = CriterionResult("a", Status.MET, weight=3, required=True)
    missing = CriterionResult("b", Status.MISSING, weight=1)
    unknown = CriterionResult("c", Status.UNKNOWN, weight=5)
    assert fit_from([met, missing])[0] is Fit.HIGH          # 3/4 = 0,75
    assert fit_from([met, unknown])[0] is Fit.HIGH          # lo desconocido no cuenta
    assert fit_from([unknown]) == (Fit.UNKNOWN, None) and fit_from([]) == (Fit.UNKNOWN, None)
    lacking = CriterionResult("d", Status.MISSING, weight=1, required=True)
    assert fit_from([CriterionResult("e", Status.MET, weight=9), lacking])[0] is Fit.MEDIUM   # falta un imprescindible
    half = fit_from([CriterionResult("f", Status.MET), CriterionResult("g", Status.MISSING)])
    assert half[0] is Fit.MEDIUM and half[1] == 0.5
    assert fit_from([CriterionResult("h", Status.MISSING), CriterionResult("i", Status.MISSING),
                     CriterionResult("j", Status.MET)])[0] is Fit.LOW


def test_a_matching_job_gets_a_high_fit_and_a_summary():
    result = evaluate(job(), profile(nice=["SQL"]))
    assert result.fit is Fit.HIGH and result.score is not None and result.score >= 0.75
    assert result.summary == f"{result.count(Status.MET)}/{result.count(Status.MET) + result.count(Status.MISSING)}"
    assert evaluate(job(description="", full_description=False, title="x"), Profile(name="vacío")).summary == "—"


def test_categories_look_at_the_title_first_then_at_the_text():
    cats = [Category("CRM", ["crm", "salesforce"]), Category("Data PO", ["data", "datos"])]
    mine = profile(categories=cats)
    assert categorize(job(title="Product Owner Data", description="usamos CRM"), mine) == "Data PO"
    assert categorize(job(title="Product Owner", description="usamos Salesforce"), mine) == "CRM"
    assert categorize(job(title="Chef", description="cocina"), mine) == ""


def test_experience_ignores_ages_and_studies_come_from_the_description():
    text = ("Se requiere titulación universitaria en informática. Las personas candidatas deben ser menores de "
            "30 años y no tener más de un año de experiencia. " * 2)
    result = evaluate(job(description=text), profile(studies="degree"))
    assert by_name(result, "Experiencia").status is Status.UNKNOWN                 # no es una edad mínima
    assert by_name(result, "Estudios").status is Status.MET
    assert by_name(evaluate(job(description=text), profile(studies="fp")), "Estudios").status is Status.MISSING
    summary = evaluate(job(description=text, full_description=False), profile(studies="degree"))
    assert by_name(summary, "Estudios").status is Status.UNKNOWN                   # una ficha resumida no cuenta
