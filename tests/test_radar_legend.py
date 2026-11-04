import pytest

gi = pytest.importorskip("gi")
cairo = pytest.importorskip("cairo")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from grepleo.ats import AtsEstimate
from grepleo.detail import BULLET  # noqa: F401 - comprueba que el módulo se importa con GTK cargado
from grepleo.matching import evaluate
from grepleo.models import Fit, Job
from grepleo.profiles import Profile, RadarAxis, SkillRadar
from grepleo.radar import RadarData, build_radars
from grepleo.ui.detail_view import DetailView
from grepleo.ui.radar_legend import build_ats, build_legend
from grepleo.ui.radar_panel import RadarPanel


def texts(widget):
    """Todo el texto de los Gtk.Label de un widget, sin el marcado."""
    found = []
    if isinstance(widget, Gtk.Label):
        found.append(widget.get_text())
    child = widget.get_first_child()
    while child is not None:
        found.extend(texts(child))
        child = child.get_next_sibling()
    return found


RADAR = RadarData("Cloud", ["AWS", "Terraform", "Helm", "Kubernetes"], [9, 4, 3, 2], [10, 7, 0, None],
                  ["la pide como requisito o en el título", "la valora como deseable", "no aparece en la oferta",
                   "ficha resumida: no se puede saber"])


def test_the_legend_explains_the_polygons_the_overlap_and_every_axis():
    legend = "\n".join(texts(build_legend(RADAR, Fit.MEDIUM)))
    assert "Tú" in legend and "Lo que pide la oferta" in legend and "ficha resumida" not in legend.split("Solape")[0]
    assert "Solape 76 %" in legend and "cubres 13 de 17 puntos" in legend          # (9+4) de (10+7)
    assert "tú 9 · pide 10" in legend and "te falta 1 punto" in legend and "te faltan 3 puntos" in legend
    assert "no lo pide" in legend and "no se sabe" in legend and "pide ?" in legend
    assert "Lo que más te falta: Terraform (−3), AWS (−1)" in legend
    assert "la pide como requisito o en el título" in legend


def test_the_legend_of_a_radar_the_offer_does_not_ask_anything_of_says_so():
    empty = RadarData("X", ["a", "b", "c"], [5, 5, 5], [0, None, 0], ["", "", ""])
    legend = "\n".join(texts(build_legend(empty, Fit.LOW)))
    assert "no pide nada medible" in legend and "Lo que más te falta" not in legend


def test_the_ats_box_shows_the_percentage_the_verdict_and_where_it_comes_from():
    estimate = AtsEstimate(58, "medium", 0.5, 0.67, 0.83, found=["AWS"], missing=["Docker", "Terraform"],
                           failed=["Experiencia"], unknown=1)
    box = build_ats(estimate)
    text = "\n".join(texts(box))
    assert "Compatibilidad ATS estimada: 58 %" in text and "Puede pasar" in text and "fiabilidad media" in text
    assert "cita 1 de las 3" in text and "67 %" in text and "83 %" in text
    assert "no cumples: Experiencia" in text and "Cada uno resta un 40 %" in text
    assert "Palabras clave que tu CV no cita: Docker, Terraform" in text and "solo si son ciertas" in text
    assert "CV base (un PDF subido no se lee)" in text and "1 requisito no se puede saber" in text
    uploaded = AtsEstimate(90, "high", 1.0, 1.0, 1.0, found=["AWS"], from_upload=True)
    plain = "\n".join(texts(build_ats(uploaded)))
    assert "que subiste" in plain and "ninguno incumplido" in plain and "Palabras clave que tu CV no cita" not in plain


def test_the_ats_box_without_keyword_data_and_with_many_missing_keywords():
    summary = AtsEstimate(40, "low", None, None, 1.0, missing=[f"T{n}" for n in range(12)])
    text = "\n".join(texts(build_ats(summary)))
    assert "ficha resumida" in text and "y 4 más" in text and "poco probable" in text


def test_the_panel_puts_the_ats_box_first_and_a_legend_next_to_each_radar():
    offer = Job(key="x:1", source="x", title="DevOps", description="Requisitos:\n- AWS\n- Python\n" * 4,
                full_description=True)
    profile = Profile(name="p", must=["AWS"], radars=[
        SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Python", 4), RadarAxis("Go", 2)])])
    panel = RadarPanel()
    panel.set_data(build_radars(offer, profile), Fit.HIGH, AtsEstimate(80, "high", 1.0, 1.0, 1.0))
    assert panel.ats_box is not None and len(panel.views) == 2 and len(panel.legends) == 2
    assert "Compatibilidad ATS estimada: 80 %" in "\n".join(texts(panel.ats_box))
    panel.set_data(build_radars(offer, profile), Fit.HIGH)               # sin estimación no hay cuadro
    assert panel.ats_box is None and len(panel.legends) == 2
    panel.set_data([], Fit.UNKNOWN)
    assert panel.legends == [] and panel.ats_box is None


def test_the_offer_tab_shows_the_ats_percentage_next_to_the_fit():
    offer = Job(key="x:2", source="x", title="DevOps", description="AWS " * 40, full_description=True)
    profile = Profile(name="p", must=["AWS"])
    view = DetailView()
    view.show_job(offer, evaluate(offer, profile), profile, "—", AtsEstimate(72, "high", 1.0, 1.0, 1.0))
    buffer = view.get_buffer()
    assert "ATS ≈ 72 %" in buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
    view.show_job(offer, evaluate(offer, profile), profile, "—")
    assert "ATS" not in buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
