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
from grepleo.ui.radar_view import RadarView


def painted(view, width=320, height=240):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    view._draw(None, cairo.Context(surface), width, height)
    return surface


def count_pixels(surface):
    return sum(1 for byte in bytes(surface.get_data())[3::4] if byte)


LABELS = ["Técnicas", "Blandas", "Experiencia", "Idiomas", "Estudios"]


def test_the_radar_draws_with_and_without_an_offer_and_with_missing_data():
    view = RadarView()
    empty = count_pixels(painted(view))                       # solo la rejilla
    levels = [8, 5, 6, 7, 4]
    view.set_data(LABELS, levels, None, Fit.UNKNOWN)
    alone = count_pixels(painted(view))
    view.set_data(LABELS, levels, [6, None, 3, 8, 0], Fit.HIGH)
    both = count_pixels(painted(view))
    assert empty > 0 and alone > empty and both > alone       # cada capa añade dibujo
    assert "Técnicas: tú 8 · oferta 6" in view.get_tooltip_text()
    assert "Blandas: tú 5 · oferta ?" in view.get_tooltip_text()
    view.set_data(LABELS, levels, [10, 4, 3, 8, 0], Fit.HIGH, ["cita 10 o más tecnologías", "", "pide 3 años"])
    assert "Técnicas: tú 8 · oferta 10 (cita 10 o más tecnologías)" in view.get_tooltip_text()   # qué hay detrás
    assert "Blandas: tú 5 · oferta 4\n" in view.get_tooltip_text() + "\n" and "(pide 3 años)" in view.get_tooltip_text()


def test_any_number_of_axes_from_three_to_eight_can_be_drawn():
    view = RadarView()
    for count in (3, 4, 6, 8):
        view.set_data([f"Elemento {n}" for n in range(count)], [7.0] * count, [5.0] * count, Fit.MEDIUM)
        assert count_pixels(painted(view)) > 0
    view.set_data(["Una etiqueta larguísima que no cabe"] * 3, [5.0] * 3, None, Fit.UNKNOWN)
    painted(view)                                              # no falla con etiquetas largas


def test_the_profile_polygon_gets_more_intense_towards_the_edges():
    view = RadarView()
    view.set_data(LABELS, [10.0] * 5, None, Fit.UNKNOWN)
    surface = painted(view, 400, 400)
    data = bytes(surface.get_data())
    stride = surface.get_stride()

    def alpha(x, y):
        return data[y * stride + x * 4 + 3]
    centre, edge = alpha(200, 192), alpha(200, 192 - 105)    # cerca del vértice superior (radio 120) frente al centro
    assert edge > centre
