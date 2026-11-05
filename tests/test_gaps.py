from grepleo.gaps import Gap, find_gaps
from grepleo.matching import evaluate
from grepleo.models import Job
from grepleo.profiles import Profile, RadarAxis, SkillRadar
from grepleo.ui.gui import gap_text


def job(key, text, title="DevOps Engineer", full=True):
    return Job(key=f"x:{key}", source="x", title=title, description=text, full_description=full)


def profile(**kwargs):
    base = {"name": "DevOps", "must": ["Docker"], "nice": []}
    return Profile(**{**base, **kwargs})


def evaluations(jobs, prof):
    return {item.key: evaluate(item, prof) for item in jobs}


def test_what_is_not_in_the_profile_is_a_gap_ranked_by_how_many_offers_ask_for_it():
    jobs = [job(i, "Requisitos: experiencia con Jenkins y Docker.") for i in range(3)]
    jobs.append(job(9, "Se valora Splunk."))
    prof = profile()
    gaps = find_gaps(jobs, evaluations(jobs, prof), prof)
    names = [gap.name for gap in gaps]
    assert names[:2] == ["Jenkins", "Splunk"] and "Docker" not in names   # Docker ya está en tu perfil
    jenkins = gaps[0]
    assert jenkins.missing and jenkins.how == "no la tienes" and jenkins.offers == 3 and jenkins.required == 3


def test_a_radar_item_with_a_low_level_is_a_gap_only_where_the_offer_asks_for_more():
    radar = SkillRadar("Cloud", [RadarAxis("Azure", 2), RadarAxis("AWS", 8), RadarAxis("GCP", 7)])
    prof = profile(radars=[radar])
    jobs = [job(1, "Requisitos: Azure y AWS."), job(2, "Experiencia en AWS.")]
    gaps = {gap.name: gap for gap in find_gaps(jobs, evaluations(jobs, prof), prof)}
    assert gaps["Azure"].how == "tu nivel: 2 de 10" and gaps["Azure"].offers == 1 and not gaps["Azure"].missing
    assert "AWS" not in gaps and "GCP" not in gaps       # niveles altos: sin hueco
    assert "Cloud" not in gaps                            # lo cubren los ejes de ese radar


def test_pairs_languages_and_summaries_do_not_make_noise():
    prof = profile(must=["CI", "CD"], languages={"Inglés": "B2"})
    jobs = [job(1, "CI/CD y nivel de inglés alto."), job(2, "Jenkins", full=False)]
    names = [gap.name for gap in find_gaps(jobs, evaluations(jobs, prof), prof)]
    assert "CI/CD" not in names and "Inglés" not in names   # tienes CI y CD; el idioma está en el perfil
    assert "Jenkins" not in names                           # una ficha resumida no cuenta
    assert find_gaps([], {}, prof) == [] and find_gaps([job(3, "x", full=False)], {}, prof) == []


def test_gap_text_says_what_it_is_and_how_many_offers_ask_for_it():
    assert gap_text(Gap("Jenkins", "no la tienes", 0.0, 3, 2, 1)) == (
        "No la tienes · la piden 3 ofertas (2 como requisito, 1 de encaje alto o medio)")
    assert gap_text(Gap("Azure", "tu nivel: 2 de 10", 0.2, 1, 0, 0)) == "Tu nivel: 2 de 10 · la pide 1 oferta"
    assert gap_text(Gap("EC2", "tienes algo parecido: Azure", 0.6, 1, 0, 0)).startswith("Tienes algo parecido: Azure")


def test_strengths_are_what_you_have_and_the_offers_ask_for_most():
    from grepleo.gaps import find_strengths
    from grepleo.ui.gui import strength_text
    radar = SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Azure", 2)])
    prof = profile(must=["Docker", "Terraform"], radars=[radar])
    jobs = [job(i, "Requisitos: AWS, Docker y Azure.") for i in range(3)] + [job(9, "Docker.")]
    strengths = {item.name: item for item in find_strengths(jobs, evaluations(jobs, prof), prof)}
    assert set(strengths) == {"AWS", "Docker"}           # Azure es un hueco (nivel 2) y Terraform nadie lo cita
    assert strengths["AWS"].level == 8 and strengths["AWS"].offers == 3
    assert strengths["Docker"].level == 10 and strengths["Docker"].offers == 4     # tu nivel técnico general (10 si no lo tocas)
    assert strength_text(strengths["Docker"]).startswith("Tu nivel: 10 de 10 · la piden 4 ofertas")
    assert strength_text(strengths["AWS"]).startswith("Tu nivel: 8 de 10")
    assert find_strengths([], {}, prof) == [] and find_strengths([job(1, "x", full=False)], {}, prof) == []


def test_ci_and_cd_listed_separately_count_as_one_strength():
    from grepleo.gaps import find_strengths
    prof = profile(must=["CI", "CD", "Docker"])
    jobs = [job(1, "Requisitos: CI/CD y Docker.")]
    assert [item.name for item in find_strengths(jobs, evaluations(jobs, prof), prof)] == ["CI/CD", "Docker"]


def test_gaps_use_the_same_coverage_as_the_fit_platform_similar_and_generic_terms():
    radar = SkillRadar("Cloud", [RadarAxis("AWS", 10)])
    prof = profile(must=["Terraform", "GitHub Actions"], nice=[], radars=[radar], languages={})
    jobs = [job(i, "Requisitos:\n- Experiencia real con VPC, EC2, Azure, IaC y Jenkins en producción\n" * 3)
            for i in range(2)]
    gaps = {gap.name: gap for gap in find_gaps(jobs, evaluations(jobs, prof), prof)}
    assert "VPC" not in gaps and "EC2" not in gaps          # tener AWS cubre sus servicios (como en el encaje)
    assert "IaC" not in gaps                                # Terraform cubre el término genérico
    assert gaps["Azure"].how == "tienes algo parecido: AWS" and 0 < gaps["Azure"].credit < 1   # otra nube: a medias
    assert gaps["Jenkins"].how == "tienes algo parecido: GitHub Actions"                        # otro CI/CD: a medias


def test_a_strength_that_is_a_pair_has_the_level_of_its_weaker_half():
    from grepleo.gaps import find_strengths
    prof = profile(must=["CI", "CD"], nice=[], radars=[], languages={}, radar={"technical": 8})
    jobs = [job(1, "Requisitos:\n- CI/CD con pipelines en producción\n" * 3)]
    strengths = {item.name: item for item in find_strengths(jobs, evaluations(jobs, prof), prof)}
    assert strengths["CI/CD"].level == 8
