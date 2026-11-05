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


def test_what_the_offer_asks_is_compared_with_what_you_have():
    result = evaluate(job(), profile())
    assert by_name(result, "Scrum").status is Status.MET and by_name(result, "Power BI").status is Status.MET
    assert by_name(result, "SQL").status is Status.MET
    assert by_name(result, "Jira").status is Status.MISSING          # lo piden y no lo tienes
    assert "no la tienes" in by_name(result, "Jira").detail
    assert all(item.name != "Snowflake" for item in result.criteria)  # lo tienes y no lo piden: no cuenta
    summary = evaluate(job(description="Scrum y Azure", full_description=False), profile())
    assert by_name(summary, "Scrum").status is Status.MET              # en una ficha resumida lo citado es un mínimo
    assert by_name(summary, "Azure").status is Status.MISSING and by_name(summary, "Azure").required
    assert all(item.name != "Snowflake" for item in summary.criteria)


def test_similar_tools_and_lower_levels_give_partial_credit():
    from grepleo.profiles import RadarAxis, SkillRadar
    asked = job(description="Requisitos:\n- Experiencia con Azure y con Jenkins en producción\n" * 3)
    mine = profile(must=["AWS"], nice=["GitHub Actions"], languages={})
    result = evaluate(asked, mine)
    azure, jenkins = by_name(result, "Azure"), by_name(result, "Jenkins")
    assert azure.status is Status.PARTIAL and azure.required and "AWS" in azure.detail     # otra nube
    assert jenkins.status is Status.PARTIAL and "GitHub Actions" in jenkins.detail         # otro CI/CD
    assert 0 < azure.credit < 1 and azure.value == azure.credit
    low = profile(must=[], radars=[SkillRadar("Cloud", [RadarAxis("Azure", 3), RadarAxis("AWS", 9),
                                                        RadarAxis("GCP", 9)])])
    level = by_name(evaluate(asked, low), "Azure")
    assert level.status is Status.PARTIAL and "3 de 10" in level.detail and abs(level.credit - 0.3) < 1e-9
    assert by_name(evaluate(asked, profile(must=["Azure"])), "Azure").status is Status.MET
    pair = evaluate(job(description="Requisitos:\n- CI/CD con pipelines\n" * 3), profile(must=["CI", "CD"]))
    assert by_name(pair, "CI/CD").status is Status.MET                # «CI» y «CD» por separado cubren «CI/CD»


def test_experience_and_languages_are_compared_with_the_profile():
    assert by_name(evaluate(job(), profile(years=8)), "Experiencia").status is Status.MET
    near = by_name(evaluate(job(), profile(years=3)), "Experiencia")        # faltan dos años: se cede en parte
    assert near.status is Status.PARTIAL and near.credit == 0.3 and "5 años" in near.detail and "3 años" in near.detail
    far = by_name(evaluate(job(), profile(years=1)), "Experiencia")
    assert far.status is Status.MISSING
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


def hard(status, weight=1, **extra):
    return CriterionResult("x", status, weight=weight, group="hard", **extra)


def test_fit_levels():
    unknown = CriterionResult("c", Status.UNKNOWN, weight=5)
    assert fit_from([hard(Status.MET, 9), hard(Status.MISSING, 1)])[0] is Fit.HIGH       # 0,9
    assert fit_from([hard(Status.MET, 3), hard(Status.MET, 3), unknown])[0] is Fit.HIGH   # lo desconocido no cuenta
    assert fit_from([unknown]) == (Fit.UNKNOWN, None) and fit_from([]) == (Fit.UNKNOWN, None)
    # un requisito que falta resta lo que pesa, pero ya no fija el encaje: las empresas ceden
    lacking = hard(Status.MISSING, 1, required=True)
    assert fit_from([hard(Status.MET, 9), lacking])[0] is Fit.HIGH
    partial = fit_from([hard(Status.MET, 4), hard(Status.PARTIAL, 4, credit=0.5), hard(Status.MET, 4)])
    assert partial[0] is Fit.HIGH and abs(partial[1] - 10 / 12) < 1e-9
    half = fit_from([hard(Status.MET, 3), hard(Status.MISSING, 3)])
    assert half[0] is Fit.LOW and half[1] == 0.5 or half[0] is Fit.LOW
    assert fit_from([hard(Status.MET, 4), hard(Status.MISSING, 2)])[0] is Fit.MEDIUM      # 0,67
    assert fit_from([hard(Status.MISSING, 2), hard(Status.MISSING, 2), hard(Status.MET, 2)])[0] is Fit.LOW


def test_an_offer_that_asks_for_little_cannot_be_a_high_fit_on_conditions_alone():
    conditions = [CriterionResult(name, Status.MET, weight=2) for name in ("a", "b", "c", "d")]
    assert fit_from(conditions)[0] is not Fit.HIGH       # sin habilidades pedidas, el resto no basta
    assert fit_from([*conditions, hard(Status.MET, 3), hard(Status.MET, 3)])[0] is Fit.HIGH


def test_a_matching_job_gets_a_high_fit_and_a_summary():
    result = evaluate(job(), profile(nice=["SQL"]))
    assert result.fit is Fit.HIGH and result.score is not None and result.score >= 0.8
    decided = sum(result.count(status) for status in (Status.MET, Status.MISSING, Status.PARTIAL))
    assert result.summary == f"{result.count(Status.MET)}/{decided}"
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


def test_main_gaps_lists_what_the_offer_asks_and_you_do_not_cover_most_important_first():
    asked = job(description="Requisitos:\n- Experiencia con Azure, Jenkins y Jira\n" * 3)
    gaps = evaluate(asked, profile(must=["AWS"], nice=[])).main_gaps(5)
    assert gaps[:2] == ["Jenkins", "Jira"] and gaps[2] == "Azure"      # Azure resta menos: tienes otra nube (AWS)
    assert evaluate(asked, profile(must=["Azure", "Jenkins", "Jira"], nice=[])).main_gaps() == []


def test_the_title_sets_the_level_when_the_offer_gives_no_years():
    senior = evaluate(job(title="Senior DevOps Engineer", description="Scrum"), profile(years=1))
    assert by_name(senior, "Nivel del puesto").status is Status.MISSING
    near = evaluate(job(title="Lead Engineer", description="Scrum"), profile(years=3))
    assert by_name(near, "Nivel del puesto").status is Status.PARTIAL
    assert by_name(evaluate(job(title="Junior DevOps", description="Scrum"), profile(years=1)),
                   "Nivel del puesto").status is Status.MET
    assert all(item.name != "Nivel del puesto" for item in evaluate(job(title="DevOps", description="Scrum"),
                                                                       profile(years=1)).criteria)
    stated = evaluate(job(title="Senior DevOps", description="Pedimos 3 años de experiencia."), profile(years=1))
    assert all(item.name != "Nivel del puesto" for item in stated.criteria)     # ya dice los años: manda la experiencia
