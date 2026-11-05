import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from pathlib import Path

from gi.repository import GLib

from grepleo.models import Evaluation, Fit, Job
from grepleo.storage import Store
from grepleo.ui import map_page
from grepleo.ui.map_page import MapPage, best_fit, map_available, start_view

needs_map = pytest.mark.skipif(not map_available(), reason="libshumate (gir1.2-shumate-1.0) no está instalado")


def job(key, location, title="DevOps"):
    return Job(key=f"x:{key}", source="x", title=title, company=f"Empresa {key}", location=location)


def evaluation(fit):
    return Evaluation(fit, {Fit.HIGH: 0.9, Fit.MEDIUM: 0.6, Fit.LOW: 0.2, Fit.UNKNOWN: None}[fit])


def settle(times=40):
    context = GLib.MainContext.default()
    for _attempt in range(times):
        while context.iteration(False):
            pass
        GLib.usleep(10000)


def test_a_point_takes_the_color_of_the_best_offer_and_the_view_frames_the_points():
    assert best_fit([Fit.LOW, Fit.HIGH, Fit.MEDIUM]) == Fit.HIGH and best_fit([Fit.LOW, Fit.UNKNOWN]) == Fit.LOW
    assert best_fit([]) == Fit.UNKNOWN
    lat, lon, zoom = start_view([((40.4, -3.7), 5), ((41.4, 2.2), 2)])           # Madrid y Barcelona
    assert 40.4 < lat < 41.4 and -3.7 < lon < 2.2 and 4 <= zoom <= 7
    lat, lon, zoom = start_view([((40.4, -3.7), 1), ((38.9, -77.0), 9)])         # España y Estados Unidos: el que más tiene
    assert (lat, lon, zoom) == (38.9, -77.0, 6)
    assert start_view([((40.4, -3.7), 3)])[2] == 9                               # un solo punto: zoom de ciudad


def test_without_libshumate_the_tab_says_what_to_install(monkeypatch):
    monkeypatch.setattr(map_page, "Shumate", None)
    page = MapPage(lambda: ([], {}, None), Store(Path(":memory:")), lambda _job: None)
    assert page.map is None and not map_available()
    page.refresh()                                                            # no hace nada ni falla


@needs_map
def test_the_map_shows_one_pin_per_known_place_coloured_by_fit_and_a_popover_with_its_offers():
    store = Store(Path(":memory:"))
    store.save_place("Madrid", (40.4168, -3.7038))
    store.save_place("Barcelona", (41.3874, 2.1686))
    store.save_place("Ninguna parte", None)                                   # preguntado y no existe: sin punto
    jobs = [job(1, "Madrid"), job(2, "Madrid"), job(3, "Barcelona"), job(4, "En remoto"), job(5, "Ninguna parte")]
    fits = {"x:1": Fit.LOW, "x:2": Fit.HIGH, "x:3": Fit.MEDIUM}
    evaluations = {key: evaluation(fit) for key, fit in fits.items()}
    picked = []
    page = MapPage(lambda: (jobs, evaluations, None), store, picked.append)
    page.refresh()
    assert len(page._pins) == 2
    assert page._without_place == 1                                           # el remoto no es un lugar
    classes = {pin.get_tooltip_text(): [c for c in pin.get_css_classes() if c.startswith("map-pin-")]
               for pin, _popover in page._pins}
    assert classes["Madrid · 2"] == ["map-pin-high"] and classes["Barcelona · 1"] == ["map-pin-medium"]
    assert page._pins[0][0].get_text() == "2" and page._pins[1][0].get_text() == ""     # el número, solo si hay varias
    assert "3 de 5 ofertas en el mapa" in page.status.get_text() and "1 sin ubicación" in page.status.get_text()
    madrid = page._pins[0][1]
    buttons, child = [], madrid.get_child().get_first_child()
    while child is not None:                                                  # en el orden en que se ven
        if isinstance(child, Gtk.Button):
            buttons.append(child)
        child = child.get_next_sibling()
    assert len(buttons) == 2 and "Empresa 2" in buttons[0].get_child().get_text()       # la de mejor encaje, primero
    buttons[0].emit("clicked")
    assert [item.key for item in picked] == ["x:2"]


@needs_map
def test_unknown_places_are_asked_in_the_background_cached_and_added_as_they_arrive(monkeypatch):
    store = Store(Path(":memory:"))
    asked = []

    class FakeGeocoder:
        def lookup(self, place):
            asked.append(place)
            return {"Madrid": (40.4, -3.7), "Nowhere": None}[place]

    monkeypatch.setattr(map_page, "Geocoder", FakeGeocoder)
    real = map_page.geocode_places
    monkeypatch.setattr(map_page, "geocode_places",
                        lambda places, geocoder, on_result, cancelled: real(places, geocoder, on_result, cancelled,
                                                                           pause=0, sleep=lambda _s: None))
    jobs = [job(1, "Madrid"), job(2, "Nowhere")]
    page = MapPage(lambda: (jobs, {}, None), store, lambda _job: None)
    page.refresh()
    settle()
    assert sorted(asked) == ["Madrid", "Nowhere"] and len(page._pins) == 1
    assert store.cached_places(["Madrid", "Nowhere"]) == {"Madrid": (40.4, -3.7), "Nowhere": None}   # se guarda todo
    page.invalidate()
    page.refresh()                                                            # la segunda vez no pregunta nada
    settle()
    assert sorted(asked) == ["Madrid", "Nowhere"] and len(page._pins) == 1


@needs_map
def test_a_network_failure_keeps_what_is_known_and_says_so(monkeypatch):
    store = Store(Path(":memory:"))
    store.save_place("Madrid", (40.4, -3.7))

    class Failing:
        def lookup(self, place):
            from grepleo.geocode import GeocodeError
            raise GeocodeError("sin red")

    monkeypatch.setattr(map_page, "Geocoder", Failing)
    jobs = [job(1, "Madrid"), job(2, "Valencia")]
    page = MapPage(lambda: (jobs, {}, None), store, lambda _job: None)
    page.refresh()
    settle()
    assert len(page._pins) == 1 and "no se pudo seguir buscando: sin red" in page.status.get_text()
    assert store.cached_places(["Valencia"]) == {}                            # un fallo de red no se guarda como «no existe»


@needs_map
def test_the_tiles_need_no_key_and_the_dark_theme_inverts_them_while_the_pins_keep_their_color():
    """CARTO pasó a exigir una clave (el mapa se llenaba de «API KEY REQUIRED»): se usan las imágenes de OpenStreetMap, que
    son claras; en el tema oscuro se invierte el mapa y cada punto se invierte otra vez para conservar su color."""
    store = Store(Path(":memory:"))
    store.save_place("Madrid", (40.4, -3.7))
    jobs = [job(1, "Madrid")]
    dark = MapPage(lambda: (jobs, {}, None), store, lambda _job: None, dark=True)
    light = MapPage(lambda: (jobs, {}, None), store, lambda _job: None)
    assert dark.map.get_map_source().get_id() == "openstreetmap" == light.map.get_map_source().get_id()
    assert "tile.openstreetmap.org" in map_page.TILES[2] and "carto" not in map_page.TILES[2].lower()
    assert dark.map.get_map().has_css_class("map-dark") and not light.map.get_map().has_css_class("map-dark")
    dark.refresh()
    light.refresh()
    assert dark._pins[0][0].has_css_class("map-pin-undo") and not light._pins[0][0].has_css_class("map-pin-undo")
