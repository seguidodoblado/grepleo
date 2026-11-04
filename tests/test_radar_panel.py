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

from grepleo.models import Fit
from grepleo.radar import RadarData
from grepleo.ui.radar_panel import RadarPanel, percent


def test_percent_and_the_panel_show_one_radar_per_topic_with_its_overlap():
    assert percent(None) == "—" and percent(0.826) == "83 %" and percent(1) == "100 %"
    panel = RadarPanel()
    assert not panel.views                                     # sin oferta: solo un aviso
    radars = [RadarData("General", ["a", "b", "c"], [8, 4, 6], [6, 8, 6]),
              RadarData("Cloud", ["AWS", "Docker", "Helm"], [9, 5, 2], [10, 7, 0]),
              RadarData("Sin demanda", ["x", "y", "z"], [5, 5, 5], [0, None, 0])]
    panel.set_data(radars, Fit.HIGH)
    assert len(panel.views) == 3
    total = (6 + 4 + 6 + 9 + 5) / (6 + 8 + 6 + 10 + 7)
    assert f"{round(total * 100)} %" in panel.summary.get_text()
    assert "con datos en 8 de 9 ejes" in panel.summary.get_text()       # uno de los ejes es «?»
    panel.set_data([], Fit.UNKNOWN)
    assert panel.views == []
    panel.set_data([radars[2]], Fit.LOW)                       # la oferta no pide nada medible
    assert "no pide nada" in panel.summary.get_text()
