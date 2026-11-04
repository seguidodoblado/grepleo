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


def test_the_minimap_has_one_thumbnail_per_radar_coloured_by_overlap_and_scrolls_to_it():
    from grepleo.ui.radar_minimap import overlap_class
    assert [overlap_class(value) for value in (None, 0.2, 0.5, 0.9)] == ["none", "low", "medium", "high"]
    panel = RadarPanel()
    radars = [RadarData("General", ["a", "b", "c"], [8, 4, 6], [6, 8, 6]),
              RadarData("Cloud", ["AWS", "Docker", "Helm"], [9, 5, 2], [10, 7, 0]),
              RadarData("Sin demanda", ["x", "y", "z"], [5, 5, 5], [0, None, 0])]
    panel.set_data(radars, Fit.HIGH)
    assert panel.minimap is not None and len(panel.minimap.thumbs) == 3
    assert len(panel.cards) == 3 and panel.cards[1].has_css_class("radar-card-high")
    first, second = panel.minimap.thumbs[0], panel.minimap.thumbs[1]
    assert first.get_first_child().get_size_request()[0] > second.get_first_child().get_size_request()[0]   # el general, mayor
    assert second.has_css_class("radar-thumb-high") and panel.minimap.thumbs[2].has_css_class("radar-thumb-none")
    assert "Cloud" in second.get_tooltip_text() and "solape" in second.get_tooltip_text()
    assert panel.scroll_to_radar(2) is False and panel.scroll_to_radar(9) is False      # fuera de rango: no hace nada
    panel.set_data(radars[:1], Fit.HIGH)
    assert panel.minimap is None                                                       # con un solo radar no hay minimapa
