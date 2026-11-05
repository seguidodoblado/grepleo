from grepleo.models import Job
from grepleo.profiles import Profile
from grepleo.radar import AXES, SCALE, data_levels, offer_demand

TEXT = ("Buscamos DevOps con AWS, Terraform, Docker y Kubernetes. Trabajo en equipo y liderazgo. "
        "Mínimo 3 años de experiencia. Grado en informática. Inglés C1. " * 3)


def job(**changes):
    base = {"key": "x:1", "source": "x", "title": "DevOps", "description": TEXT, "full_description": True}
    base.update(changes)
    return Job(**base)


def test_your_side_of_experience_languages_and_studies_comes_from_the_profile():
    profile = Profile(name="p", years=8, studies="degree", languages={"Inglés": "B2", "Francés": "A2"})
    levels = data_levels(profile)
    assert set(levels) == {"experience", "languages", "studies"} and levels["experience"] == 8
    assert round(levels["languages"], 1) == round(4 * SCALE / 6, 1) and round(levels["studies"], 1) == 6.7
    assert data_levels(Profile(name="vacío", years=40))["experience"] == SCALE        # nunca pasa de 10


def test_technical_and_soft_are_what_you_cover_of_what_the_offer_cites_at_the_same_height():
    from grepleo.radar import general_radar
    profile = Profile(name="p", must=["AWS", "Docker"], nice=["Terraform"], soft_must=["Liderazgo"],
                      skill_levels={"aws": 10, "docker": 10, "terraform": 5, "liderazgo": 10})
    radar = general_radar(job(), profile)
    demand = dict(zip(AXES, radar.demand, strict=True))
    mine = dict(zip(AXES, radar.levels, strict=True))
    # cita AWS, Terraform, Docker y Kubernetes (4 tecnologías, todas «mencionadas», que pide 5): cubres AWS, Docker y
    # Terraform (nivel 5 de 5) y Kubernetes no la tienes: 3 de 4, a la altura de lo que pide (4)
    assert demand["technical"] == 4 and abs(mine["technical"] - 3.0) < 1e-9
    assert demand["soft"] == 4 and abs(mine["soft"] - 2.0) < 1e-9          # cita liderazgo y trabajo en equipo: cubres uno
    assert "cubres el 75 %" in radar.notes[0]
    assert radar.levels[AXES.index("experience")] == 0 and radar.levels[AXES.index("studies")] == 0


def test_the_offer_demand_uses_the_same_scale():
    demand = offer_demand(job(), Profile(name="p"))
    assert demand["experience"] == 3 and abs(demand["studies"] - 2 * SCALE / 3) < 1e-9      # grado = 2 de 3
    assert demand["languages"] == 5 * SCALE / 6           # C1
    assert demand["technical"] >= 4 and demand["soft"] == 4     # trabajo en equipo + liderazgo
    assert all(value is None or 0 <= value <= SCALE for value in demand.values())


def test_a_summary_card_does_not_prove_anything_is_missing():
    summary = job(full_description=False, description="Scrum", experience_text="Al menos 2 años")
    demand = offer_demand(summary, Profile(name="p"))
    assert demand["technical"] is None and demand["soft"] is None and demand["studies"] is None
    assert demand["experience"] == 2
    bare = offer_demand(job(description="Un puesto sin requisitos escritos. " * 5), Profile(name="p"))
    assert bare["experience"] is None and bare["studies"] == 0 and bare["languages"] == 0


def test_polygon_points_go_around_from_the_top_and_scale_with_the_value():
    from grepleo.radar import polygon_points
    full = polygon_points([SCALE] * 5, 100, 100, 50)
    assert len(full) == 5 and abs(full[0][0] - 100) < 1e-9 and abs(full[0][1] - 50) < 1e-9     # el primer eje, arriba
    half = polygon_points([SCALE / 2] * 5, 100, 100, 50)
    assert abs(half[0][1] - 75) < 1e-9 and all(abs(point[0] - 100) <= 25 + 1e-9 for point in half)
    assert polygon_points([0] * 5, 10, 20, 50) == [(10.0, 20.0)] * 5


OFFER = """Buscamos un perfil DevOps para plataforma cloud.

Requisitos:
- Experiencia con AWS y Docker
- Python o Bash

Se valorará:
- Terraform
- Kubernetes (deseable)

Ofrecemos:
- Teletrabajo. Trabajamos con Jira.
"""


def test_the_demand_of_a_term_is_10_as_a_requirement_7_as_nice_5_if_only_mentioned_and_0_if_absent():
    from grepleo.radar import term_demand
    offer = job(title="Ingeniero Cloud", description=OFFER, full_description=True)
    assert term_demand(offer, "AWS|amazon web services") == 10          # en «Requisitos»
    assert term_demand(offer, "Python") == 10
    assert term_demand(offer, "Terraform") == 7                        # bajo «Se valorará»
    assert term_demand(offer, "Kubernetes") == 7
    assert term_demand(offer, "Jira") == 5                             # solo mencionado, bajo «Ofrecemos»
    assert term_demand(offer, "Go|golang") == 0                        # no aparece
    assert term_demand(offer, "Cloud") == 10                           # en el título
    assert term_demand(offer, "   ") is None


def test_a_cue_inside_the_line_overrides_the_section_and_a_summary_card_cannot_prove_absence():
    from grepleo.radar import term_demand
    text = "Requisitos:\n- Conocimientos de Ansible (se valorará)\n- Linux imprescindible\n\nOfrecemos:\n- Bash es un plus\n"
    offer = job(description=text * 2, full_description=True)
    assert term_demand(offer, "Ansible") == 7 and term_demand(offer, "Linux") == 10 and term_demand(offer, "Bash") == 7
    summary = job(title="Técnico de soporte", description="Scrum", full_description=False)
    assert term_demand(summary, "Scrum") is None                       # sin descripción completa: no se sabe
    assert term_demand(job(title="DevOps AWS", full_description=False), "AWS") == 10     # pero el título sí cuenta


def test_overlap_is_how_much_of_what_the_offer_asks_you_cover():
    from grepleo.radar import RadarData, overlap, total_overlap
    assert overlap([8, 3], [6, 5]) == (6 + 3) / (6 + 5)                # cubres 6 de 6 y 3 de 5
    assert overlap([8, 3, 9], [10, None, 0]) == 8 / 10                 # sin dato o sin demanda, no cuentan
    assert overlap([5, 5], [0, None]) is None                          # la oferta no pide nada medible
    first = RadarData("A", ["x", "y"], [10, 0], [10, 10])              # 10 de 20
    second = RadarData("B", ["z"], [10], [10])                         # 10 de 10
    assert first.overlap == 0.5 and total_overlap([first, second]) == 20 / 30


def test_topic_radars_need_three_to_eight_axes_and_the_general_one_comes_first():
    from grepleo.profiles import RadarAxis, SkillRadar
    from grepleo.radar import build_radars
    offer = job(description=OFFER, full_description=True)
    profile = Profile(name="p", years=2, radars=[
        SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Terraform", 4), RadarAxis("Kubernetes", 2)]),
        SkillRadar("Corto", [RadarAxis("AWS", 8), RadarAxis("Docker", 5)]),                  # menos de 3: no sale
        SkillRadar("Largo", [RadarAxis(f"T{n}", 5) for n in range(12)])])                     # más de 8: se recorta
    radars = build_radars(offer, profile)
    assert [radar.title for radar in radars] == ["General", "Cloud", "Largo"]
    cloud = radars[1]
    assert cloud.labels == ["AWS", "Terraform", "Kubernetes"] and cloud.levels == [8, 4, 2]
    assert cloud.demand == [10, 7, 7] and round(cloud.overlap, 3) == round((8 + 4 + 2) / 24, 3)
    assert len(radars[2].labels) == 8


def test_axes_are_written_one_per_line_with_synonyms_and_a_level():
    from grepleo.profiles import RadarAxis, format_axes, parse_axes
    axes = parse_axes("AWS|amazon web services = 8\nDocker\n  \nPython = 11\nGit = x\nKubernetes=0\n= 5")
    assert axes == [RadarAxis("AWS|amazon web services", 8), RadarAxis("Docker", 5), RadarAxis("Python", 5),
                    RadarAxis("Git", 5), RadarAxis("Kubernetes", 0)]
    assert axes[0].name == "AWS" and parse_axes(format_axes(axes)) == axes


def test_a_profile_with_topic_radars_round_trips_and_tolerates_garbage():
    from grepleo.profiles import RadarAxis, SkillRadar
    profile = Profile(name="p", radars=[SkillRadar("Cloud", [RadarAxis("AWS|amazon", 8), RadarAxis("Docker", 3)])])
    assert Profile.from_dict(profile.to_dict()) == profile
    odd = Profile.from_dict({"name": "x", "radars": [3, {"name": ""}, {"name": "Ok", "axes": [
        {"spec": "A", "level": 99}, {"spec": "", "level": 1}, "no", {"spec": "B", "level": True}]}]})
    assert odd.radars == [SkillRadar("Ok", [RadarAxis("A", 5), RadarAxis("B", 5)])]
    assert Profile.from_dict({"name": "y", "radars": "no"}).radars == []


def test_radars_are_proposed_from_the_profile_skills():
    from grepleo.radar import suggest_radars
    profile = Profile(name="p", must=["AWS", "Docker", "Terraform", "Python", "Bash", "Scrum"],
                      nice=["Kubernetes", "SQL", "Linux", "Jenkins"],
                      soft_must=["Liderazgo"], soft_nice=["Comunicación", "Empatía"])
    radars = {radar.name: radar for radar in suggest_radars(profile)}
    assert [axis.name for axis in radars["Cloud"].axes] == ["AWS", "Docker", "Terraform", "Kubernetes"]
    assert [axis.level for axis in radars["Cloud"].axes] == [7, 7, 7, 5]       # imprescindible 7, deseable 5
    assert "Lenguajes" in radars and [axis.name for axis in radars["Lenguajes"].axes] == ["Python", "Bash", "SQL"]
    assert [axis.name for axis in radars["Blandas"].axes] == ["Liderazgo", "Comunicación", "Empatía"]
    assert not any(len(radar.axes) < 3 for radar in radars.values())
    assert suggest_radars(Profile(name="vacío")) == []


def test_known_axes_counts_how_many_axes_could_be_measured():
    from grepleo.radar import RadarData, known_axes
    radars = [RadarData("A", ["x", "y", "z"], [1, 2, 3], [5, None, 0]), RadarData("B", ["p"], [4], [None])]
    assert known_axes(radars) == (2, 4) and known_axes([]) == (0, 0)


def test_drawn_values_never_collapse_a_polygon_to_a_line():
    from grepleo.radar import MIN_DRAWN, SCALE, drawn_value, polygon_points
    assert drawn_value(0) == MIN_DRAWN and drawn_value(None) == MIN_DRAWN and drawn_value(-3) == MIN_DRAWN
    assert drawn_value(6.5) == 6.5 and drawn_value(99) == SCALE
    points = polygon_points([drawn_value(value) for value in (0, None, 0, 0, 8)], 100, 100, 50)
    assert len({(round(x), round(y)) for x, y in points}) == 5      # cinco vértices distintos: un pentágono


def test_the_legend_rows_say_for_each_axis_whether_you_cover_it_and_by_how_much_you_fall_short():
    from grepleo.radar import (
        COVERED,
        MISSING,
        NOT_ASKED,
        UNKNOWN,
        RadarData,
        coverage_points,
        legend_rows,
        main_gaps,
    )
    radar = RadarData("Cloud", ["AWS", "Terraform", "Helm", "Kubernetes", "Git"], [9, 4, 3, 2, 5],
                      [10, 7, 0, None, 5], ["a", "b", "c", "d", "e"])
    rows = {row.label: row for row in legend_rows(radar)}
    assert rows["AWS"].status == MISSING and rows["AWS"].gap == 1           # tiene 9 y piden 10
    assert rows["Terraform"].status == MISSING and rows["Terraform"].gap == 3
    assert rows["Helm"].status == NOT_ASKED and rows["Kubernetes"].status == UNKNOWN
    assert rows["Git"].status == COVERED and rows["Git"].gap == 0 and rows["Git"].note == "e"
    assert coverage_points(radar) == (9 + 4 + 5, 10 + 7 + 5)                  # 18 de 22
    assert [row.label for row in main_gaps(radar)] == ["Terraform", "AWS"]      # de más a menos
    assert main_gaps(radar, limit=1)[0].label == "Terraform"
    assert main_gaps(RadarData("x", ["a"], [9], [3])) == []


def test_the_demand_scale_is_explained_in_words_for_topic_radars():
    from grepleo.radar import demand_note
    assert "requisito" in demand_note(10) and "deseable" in demand_note(7) and "menciona" in demand_note(5)
    assert "no aparece" in demand_note(0) and "no se puede saber" in demand_note(None)


def test_the_general_radar_says_what_is_behind_each_axis():
    from grepleo.profiles import RadarAxis, SkillRadar
    from grepleo.radar import build_radars
    offer = job(description=OFFER + "\nMínimo 3 años de experiencia.\n", full_description=True)
    profile = Profile(name="p", years=2, studies="degree", languages={"Inglés": "B2"},
                      radars=[SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Terraform", 4), RadarAxis("Go", 2)])])
    general, cloud = build_radars(offer, profile)
    notes = dict(zip(general.labels, general.notes, strict=True))
    assert "tecnolog" in notes["Técnicas"] and notes["Experiencia"] == "pide 3 años de experiencia"
    assert notes["Idiomas"] == "no pide idiomas" and notes["Estudios"] == "no pide estudios concretos"
    assert cloud.notes == ["la pide como requisito o en el título", "la valora como deseable", "no aparece en la oferta"]
    summary = job(full_description=False, description="Scrum")
    assert all("no se puede saber" in note for note in build_radars(summary, profile)[1].notes)
    silent = build_radars(job(description=OFFER, full_description=True), profile)[0]
    assert dict(zip(silent.labels, silent.notes, strict=True))["Experiencia"] == "no dice cuánta experiencia pide"
    english = job(description=OFFER + "\nSe requiere inglés C1. Titulación: grado universitario.\n", full_description=True)
    notes = dict(zip(general.labels, build_radars(english, profile)[0].notes, strict=True))
    assert notes["Idiomas"] == "pide nivel C1" and notes["Estudios"] == "pide grado"


def test_the_technical_axis_says_how_many_technologies_the_offer_cites_and_that_ten_is_a_cap():
    from grepleo.radar import _general_notes
    notes = _general_notes({"technical": 10.0, "soft": 0.0, "experience": 3.0, "languages": 0.0, "studies": 0.0})
    assert notes[0] == "cita 10 o más tecnologías"
    assert _general_notes({"technical": 4.0, "soft": 0.0, "experience": 3.0, "languages": 0.0, "studies": 0.0})[0] == "cita 4 tecnologías"
