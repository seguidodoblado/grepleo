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
    assert jenkins.missing and jenkins.offers == 3 and jenkins.required == 3


def test_a_radar_item_with_a_low_level_is_a_gap_only_where_the_offer_asks_for_more():
    radar = SkillRadar("Cloud", [RadarAxis("Azure", 2), RadarAxis("AWS", 8), RadarAxis("GCP", 7)])
    prof = profile(radars=[radar])
    jobs = [job(1, "Requisitos: Azure y AWS."), job(2, "Experiencia en AWS.")]
    gaps = {gap.name: gap for gap in find_gaps(jobs, evaluations(jobs, prof), prof)}
    assert gaps["Azure"].level == 2 and gaps["Azure"].offers == 1 and not gaps["Azure"].missing
    assert "AWS" not in gaps and "GCP" not in gaps       # niveles de 7 o más: sin hueco
    assert "Cloud" not in gaps                            # lo cubren los ejes de ese radar


def test_pairs_languages_and_summaries_do_not_make_noise():
    prof = profile(must=["CI", "CD"], languages={"Inglés": "B2"})
    jobs = [job(1, "CI/CD y nivel de inglés alto."), job(2, "Jenkins", full=False)]
    names = [gap.name for gap in find_gaps(jobs, evaluations(jobs, prof), prof)]
    assert "CI/CD" not in names and "Inglés" not in names   # tienes CI y CD; el idioma está en el perfil
    assert "Jenkins" not in names                           # una ficha resumida no cuenta
    assert find_gaps([], {}, prof) == [] and find_gaps([job(3, "x", full=False)], {}, prof) == []


def test_gap_text_says_what_it_is_and_how_many_offers_ask_for_it():
    assert gap_text(Gap("Jenkins", None, 3, 2, 1)) == (
        "No está en tu perfil · la piden 3 ofertas (2 como requisito, 1 de encaje alto o medio)")
    assert gap_text(Gap("Azure", 2, 1, 0, 0)) == "Tu nivel: 2 de 10 · la pide 1 oferta"
