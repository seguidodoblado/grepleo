from grepleo.market import build_market, relevant_jobs
from grepleo.matching import evaluate
from grepleo.models import Fit, Job
from grepleo.profiles import Profile, RadarAxis, SkillRadar


def job(key, text, title="DevOps Engineer", full=True):
    return Job(key=f"x:{key}", source="x", title=title, description=text, full_description=full)


def profile():
    radar = SkillRadar("Cloud", [RadarAxis("AWS", 9), RadarAxis("Azure", 3), RadarAxis("GCP", 5)])
    return Profile(name="p", must=["AWS"], radars=[radar])


def test_the_market_radars_use_the_mean_demand_among_the_offers_that_ask_and_weight_by_how_many_ask():
    jobs = [job(1, "Requisitos:\n- Experiencia con AWS y Azure en producción\n" * 3),
            job(2, "Requisitos:\n- Experiencia con AWS en producción\n" * 3),
            job(3, "Trabajamos en un equipo ágil con mucha ilusión. " * 6),
            job(4, "Solo una ficha resumida", full=False)]
    market = build_market(jobs, profile())
    assert market.offers == 3 and market.seen == 4 and [r.title for r in market.radars] == ["General", "Cloud"]
    cloud = market.radars[1]
    assert cloud.labels == ["AWS", "Azure", "GCP"]
    assert cloud.demand == [10.0, 10.0, 0.0]                     # media entre las que lo piden: no se diluye con la que no
    assert cloud.weights is not None and [round(w, 2) for w in cloud.weights] == [0.67, 0.33, 0.0]
    assert "67 %" in cloud.notes[0] and "33 %" in cloud.notes[1] and cloud.notes[2] == "ninguna oferta lo pide"
    # AWS (nivel 9 frente a 10, el 67 %) y Azure (3 frente a 10, el 33 %): (9×0,67 + 3×0,33) / (10×0,67 + 10×0,33)
    assert abs(cloud.overlap - (9 * 2 / 3 + 3 / 3) / 10) < 1e-9
    assert len(market.radars[0].labels) == 5 and market.radars[0].weights is not None


def test_without_full_offers_the_market_is_empty_and_relevant_keeps_high_and_medium_fits():
    assert build_market([], profile()).radars == [] and build_market([job(1, "x", full=False)], profile()).offers == 0
    good = job(1, "Requisitos:\n- AWS, Docker y Terraform en producción\n" * 4)
    bad = job(2, "Cocinar paella para cuarenta personas. " * 6, title="Cocinero")
    prof = Profile(name="p", must=["AWS", "Docker", "Terraform"], years=5)
    evaluations = {item.key: evaluate(item, prof) for item in (good, bad)}
    assert evaluations[good.key].fit in (Fit.HIGH, Fit.MEDIUM) and evaluations[bad.key].fit not in (Fit.HIGH, Fit.MEDIUM)
    assert [item.key for item in relevant_jobs([good, bad], evaluations)] == [good.key]
