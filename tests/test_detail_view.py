import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from grepleo.matching import evaluate
from grepleo.models import Job, WorkMode
from grepleo.profiles import Profile
from grepleo.ui.detail_view import DetailView

TEXT = """Descripción
Cloud Engineer Azure en proyecto de seguros.

Requisitos:
- Azure y Kubernetes
- Linux
Se valorará:
Terraform. Guardias de fin de semana."""


def tag_names_at(view, offset):
    buffer = view.get_buffer()
    return {tag.get_property("name") for tag in buffer.get_iter_at_offset(offset).get_tags()}


def test_show_job_writes_every_section_and_highlights_the_profile():
    job = Job(key="x:1", source="x", title="Cloud Engineer", company="ACME", location="Madrid",
              work_mode=WorkMode.HYBRID, contract="Indefinido", experience_text="3 años", posted="2026-11-04",
              description=TEXT, full_description=True)
    profile = Profile(name="p", years=4, must=["Azure|azure", "Kubernetes", "Linux"], nice=["Terraform"],
                      avoid=["guardias"])
    view = DetailView()
    view.show_job(job, evaluate(job, profile), profile, "36.000–48.000 €")
    buffer = view.get_buffer()
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    for expected in ("Cloud Engineer", "ACME · Madrid", "36.000–48.000 € · 3 años · Indefinido",
                     "Publicada el 2026-11-04", "Encaje: Alto", "Criterios", "Azure", "Descripción",
                     "•  Azure y Kubernetes", "•  Linux"):
        assert expected in text
    assert "good" in tag_names_at(view, text.index("Azure y Kubernetes") )
    assert "good" in tag_names_at(view, text.index("Terraform. Guardias") + 1)
    assert "bad" in tag_names_at(view, text.index("Guardias") + 1)
    assert "heading" in tag_names_at(view, text.index("Requisitos") + 1)


def test_show_job_without_description_and_the_placeholder():
    job = Job(key="x:2", source="x", title="Sin texto")
    view = DetailView()
    view.show_job(job, evaluate(job, Profile(name="p")), Profile(name="p"), "—")
    buffer = view.get_buffer()
    assert "Ficha resumida" in buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    view.show_message("Elige una oferta")
    assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == "Elige una oferta"


def test_a_required_skill_you_lack_is_painted_red():
    job = Job(key="x:3", source="x", title="Backend",
              description="Requisitos:\n- Experiencia real con Kubernetes y Terraform en producción\n" * 3,
              full_description=True)
    profile = Profile(name="p", must=["Terraform"])
    view = DetailView()
    evaluation = evaluate(job, profile)
    view.show_job(job, evaluation, profile, "—")
    buffer = view.get_buffer()
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    row = text.index("Kubernetes")
    assert {"missing-text", "critical"} <= tag_names_at(view, row)      # lo piden como requisito y no lo tienes
    assert "imprescindible" in text
    assert "critical" not in tag_names_at(view, text.index("Terraform —"))   # lo que sí tienes no se pinta de rojo


def test_criteria_are_split_into_hard_skills_soft_skills_and_conditions():
    job = Job(key="x:4", source="x", title="Backend", location="Madrid",
              description="Python, comunicación y liderazgo en un entorno ágil. " * 6, full_description=True)
    profile = Profile(name="p", must=["Python"], soft_must=["Liderazgo"], soft_nice=["Comunicación|communication"],
                      locations=["Madrid"], languages={"Inglés": "B2"})
    view = DetailView()
    evaluation = evaluate(job, profile)
    groups = {item.name: item.group for item in evaluation.criteria}
    assert groups["Python"] == "hard" and groups["Liderazgo"] == "soft" and groups["Comunicación"] == "soft"
    view.show_job(job, evaluation, profile, "—")
    buffer = view.get_buffer()
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    assert text.index("Habilidades técnicas") < text.index("Python —") < text.index("Habilidades blandas")
    assert text.index("Habilidades blandas") < text.index("Liderazgo —") < text.index("Condiciones")
    assert "subheading" in tag_names_at(view, text.index("Habilidades blandas") + 1)
    from grepleo.ui.detail_view import _criteria_groups
    only_hard = [item for item in evaluation.criteria if item.group == "hard"]
    assert _criteria_groups(only_hard)[0][1] == ""      # un solo grupo no necesita título


def test_met_criteria_are_green_missing_ones_red_and_unknown_ones_keep_the_normal_color():
    job = Job(key="x:5", source="x", title="Backend", description="Requisitos: Java, Spring y Docker en equipo. " * 4,
              full_description=True)
    profile = Profile(name="p", must=["Java"], avoid=["guardias"])
    view = DetailView()
    view.show_job(job, evaluate(job, profile), profile, "—")
    buffer = view.get_buffer()
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    met, missing = text.index("Java —"), text.index("Docker")           # lo que piden y no tienes lleva su marca
    assert "met-text" in tag_names_at(view, met) and "met-text" in tag_names_at(view, met + len("Java — la pi"))
    assert "missing-text" in tag_names_at(view, missing) and "met-text" not in tag_names_at(view, missing)
    summary = Job(key="x:6", source="x", title="t", description="Scrum", full_description=False)
    view.show_job(summary, evaluate(summary, profile), profile, "—")
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    unknown = text.index("Sin «guardias»")
    assert not {"met-text", "missing-text"} & tag_names_at(view, unknown)      # «?» no se pinta
