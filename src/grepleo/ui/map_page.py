"""La pestaña «Mapa»: las ofertas que estás viendo, como puntos sobre un mapa, con el color de su encaje.

El mapa lo dibuja libshumate (paquete `gir1.2-shumate-1.0`, recomendado): claro u oscuro según el tema de la aplicación
con las imágenes de OpenStreetMap (en el tema oscuro, invertidas). Cada ubicación distinta se busca una vez en Nominatim (ver
`geocode.py`) y se guarda; un punto con varias ofertas muestra cuántas son y se pone del color de la mejor.
"""
import math
from collections.abc import Callable
from threading import Thread

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

try:   # el mapa es opcional: sin el paquete, la pestaña avisa de qué instalar
    gi.require_version("Shumate", "1.0")
    from gi.repository import Shumate
except (ValueError, ImportError):
    Shumate = None

from ..geocode import Coordinates, Geocoder, clean_place, geocode_places
from ..i18n import _
from ..models import Evaluation, Fit, Job, WorkMode
from ..profiles import Profile
from ..storage import Store

TILES = ("openstreetmap", "OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")   # sin clave
LICENSE = "© OpenStreetMap contributors"
LICENSE_URI = "https://www.openstreetmap.org/copyright"
ORDER = (Fit.HIGH, Fit.MEDIUM, Fit.LOW, Fit.UNKNOWN)   # de mejor a peor: un punto con varias ofertas toma el de la mejor
LISTED = 12                                                     # ofertas que se listan al pulsar un punto
POPOVER_HEIGHT = 300                                            # alto máximo del globo; si no cabe, se desplaza


def dominant_mode(jobs: list[Job]) -> WorkMode:
    """La modalidad de la mayoría de las ofertas de un punto (si empatan, la presencial antes que la híbrida y esta antes
    que la remota); sin dato en todas, «sin dato»."""
    counts = {mode: sum(1 for job in jobs if job.work_mode is mode)
              for mode in (WorkMode.ONSITE, WorkMode.HYBRID, WorkMode.REMOTE)}
    best = max(counts.values())
    return next((mode for mode, count in counts.items() if count == best), WorkMode.UNKNOWN) if best else WorkMode.UNKNOWN


def shape_class(mode: WorkMode) -> str:
    """La forma del punto: círculo (presencial o sin dato), cuadrado redondeado (híbrido) o anillo (remoto)."""
    return {WorkMode.HYBRID: "map-pin-hybrid", WorkMode.REMOTE: "map-pin-remote"}.get(mode, "")


def map_available() -> bool:
    return Shumate is not None


def best_fit(fits: list[Fit]) -> Fit:
    return next((fit for fit in ORDER if fit in fits), Fit.UNKNOWN)


def start_view(points: list[tuple[Coordinates, int]]) -> tuple[float, float, int]:
    """Dónde mirar al abrir: (latitud, longitud, zoom). Se encuadran todos los puntos; si abarcan medio mundo (ofertas de
    España y de Estados Unidos), se mira el que más ofertas tiene."""
    lats = [lat for (lat, _lon), _count in points]
    lons = [lon for (_lat, lon), _count in points]
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 2)
    if span > 60:
        (lat, lon), _count = max(points, key=lambda item: item[1])
        return lat, lon, 6
    zoom = max(2, min(11, int(math.log2(360 / max(span, 0.4)))))
    return (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2, zoom


class MapPage(Gtk.Box):
    """`provider()` da lo que se ve ahora (ofertas, evaluaciones y perfil); `on_pick(job)` lleva a una oferta a la lista."""

    def __init__(self, provider: Callable[[], tuple[list[Job], dict[str, Evaluation], Profile | None]], store: Store,
                 on_pick: Callable[[Job], None], dark: bool = False) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8, margin_start=8, margin_end=8)
        self._provider, self._store, self._on_pick = provider, store, on_pick
        self._token = 0
        self._key: tuple | None = None
        self._coordinates: dict[str, Coordinates] = {}
        self._groups: dict[str, tuple[str, list[Job]]] = {}
        self._evaluations: dict[str, Evaluation] = {}
        self._pins: list[tuple[Gtk.Widget, Gtk.Popover]] = []
        self._fit_pending = True
        self.status = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.status.add_css_class("dim-label")
        self.append(self.status)
        self.map = None
        self._layer = None
        if Shumate is None:
            self.append(Gtk.Label(xalign=0, wrap=True, label=_(
                "Para ver el mapa instala el paquete gir1.2-shumate-1.0 (sudo apt install gir1.2-shumate-1.0) y "
                "reinicia Grepleo.")))
            return
        identifier, name, url = TILES
        source = Shumate.RasterRenderer.new_full_from_url(identifier, name, LICENSE, LICENSE_URI, 0, 19, 256,
                                                          Shumate.MapProjection.MERCATOR, url)
        self.map = Shumate.SimpleMap(vexpand=True, hexpand=True)
        overlay = Gtk.Overlay(vexpand=True, hexpand=True)
        self.map.set_map_source(source)
        self.dark = dark
        if dark:   # las imágenes de OpenStreetMap solo son claras: en el tema oscuro se invierten
            self.map.get_map().add_css_class("map-dark")
        self._layer = Shumate.MarkerLayer.new(self.map.get_viewport())
        self.map.add_overlay_layer(self._layer)
        overlay.set_child(self.map)
        overlay.add_overlay(self._build_legend(dark))
        self.append(overlay)
        note = Gtk.Label(xalign=0, wrap=True, label=_(
            "Las imágenes del mapa y la búsqueda de cada ubicación (una sola vez) son de OpenStreetMap; no se envía nada "
            "más de tus ofertas ni de tu perfil."))
        note.add_css_class("dim-label")
        self.append(note)

    @staticmethod
    def _build_legend(dark: bool = False) -> Gtk.Widget:
        """Qué significan la forma y el color de los puntos, en una esquina del mapa."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, halign=Gtk.Align.START, valign=Gtk.Align.START,
                      margin_start=10, margin_top=10)
        box.add_css_class("map-legend")
        if dark:
            box.add_css_class("map-legend-dark")

        def row(items: list[tuple[str, list[str]]]) -> Gtk.Box:
            line = Gtk.Box(spacing=10)
            for text, classes in items:
                item = Gtk.Box(spacing=5)
                swatch = Gtk.Label(valign=Gtk.Align.CENTER)
                for css in ("map-pin", "map-legend-swatch", *classes):
                    swatch.add_css_class(css)
                item.append(swatch)
                item.append(Gtk.Label(label=text))
                line.append(item)
            return line

        box.append(row([(_("Presencial"), ["map-pin-unknown"]), (_("Híbrido"), ["map-pin-unknown", "map-pin-hybrid"]),
                        (_("Remoto"), ["map-pin-unknown", "map-pin-remote"])]))
        box.append(row([(Fit.HIGH.label, ["map-pin-high"]), (Fit.MEDIUM.label, ["map-pin-medium"]),
                        (Fit.LOW.label, ["map-pin-low"]), (Fit.UNKNOWN.label, ["map-pin-unknown"])]))
        return box

    # --- datos -----------------------------------------------------------------------------------
    def invalidate(self) -> None:
        self._key = None

    def refresh(self) -> None:
        if self.map is None:
            return
        jobs, evaluations, _profile = self._provider()
        key = (tuple(job.key for job in jobs), tuple((k, v.fit.value) for k, v in sorted(evaluations.items())))
        if key == self._key:
            return
        self._key, self._evaluations = key, evaluations
        self._token += 1
        token = self._token
        groups: dict[str, tuple[str, list[Job]]] = {}
        without_place = 0
        for job in jobs:
            place = clean_place(job.location)
            if not place:
                without_place += 1
                continue
            groups.setdefault(place.casefold(), (place, []))[1].append(job)
        self._groups = groups
        known = self._store.cached_places([place for place, _jobs in groups.values()])
        self._coordinates = {place.casefold(): coords for place, coords in known.items() if coords}
        pending = [place for place, _jobs in groups.values() if place not in known]
        self._without_place, self._pending_total, self._done = without_place, len(pending), 0
        self._fit_pending = True
        self._render()
        if pending:
            self.status.set_text(self._status_text())
            Thread(target=self._geocode, args=(token, pending), daemon=True).start()

    def _geocode(self, token: int, pending: list[str]) -> None:
        def result(place: str, coordinates: Coordinates | None) -> None:
            GLib.idle_add(self._result, token, place, coordinates)

        message = geocode_places(pending, Geocoder(), result, cancelled=lambda: token != self._token)
        GLib.idle_add(self._finished, token, message)

    def _result(self, token: int, place: str, coordinates: Coordinates | None) -> bool:
        if token != self._token:
            return False
        self._store.save_place(place, coordinates)
        self._done += 1
        if coordinates:
            self._coordinates[place.casefold()] = coordinates
            self._render()
        else:
            self.status.set_text(self._status_text())
        return False

    def _finished(self, token: int, message: str) -> bool:
        if token == self._token:
            self._pending_total = self._done            # ya no queda nada por preguntar (o se paró)
            self.status.set_text(self._status_text(message))
        return False

    def _status_text(self, error: str = "") -> str:
        placed = sum(len(jobs) for key, (_place, jobs) in self._groups.items() if key in self._coordinates)
        text = _("{placed} de {total} ofertas en el mapa").format(
            placed=placed, total=sum(len(jobs) for _place, jobs in self._groups.values()) + self._without_place)
        if self._without_place:
            text += " · " + _("{count} sin ubicación (remoto o sin dato)").format(count=self._without_place)
        if self._pending_total > self._done:
            text += " · " + _("buscando ubicaciones: {done} de {total}").format(done=self._done, total=self._pending_total)
        if error:
            text += " · " + _("no se pudo seguir buscando: {error}").format(error=error)
        return text

    # --- dibujo ----------------------------------------------------------------------------------
    def _render(self) -> None:
        """Pone un punto por cada lugar conocido y encuadra el mapa la primera vez."""
        for pin, popover in self._pins:
            popover.unparent()
        self._pins = []
        self._layer.remove_all()
        points = []
        for key, (place, jobs) in self._groups.items():
            coordinates = self._coordinates.get(key)
            if coordinates is None:
                continue
            fits = [self._evaluations[job.key].fit if job.key in self._evaluations else Fit.UNKNOWN for job in jobs]
            fit = best_fit(fits)
            pin = Gtk.Label(label=str(len(jobs)) if len(jobs) > 1 else "", halign=Gtk.Align.CENTER,
                            valign=Gtk.Align.CENTER, tooltip_text=f"{place} · {len(jobs)}")
            pin.add_css_class("map-pin")
            if self.dark:
                pin.add_css_class("map-pin-undo")   # el mapa está invertido: el punto se invierte otra vez y recupera su color
            pin.add_css_class(f"map-pin-{fit.value}")
            if shape := shape_class(dominant_mode(jobs)):
                pin.add_css_class(shape)
            popover = self._popover(place, jobs, pin)
            click = Gtk.GestureClick()
            click.connect("released", lambda *_args, p=popover: p.popup())
            pin.add_controller(click)
            marker = Shumate.Marker(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            marker.set_location(*coordinates)
            marker.set_child(pin)
            self._layer.add_marker(marker)
            self._pins.append((pin, popover))
            points.append((coordinates, len(jobs)))
        self.status.set_text(self._status_text())
        if points and self._fit_pending:
            self._fit_pending = False
            lat, lon, zoom = start_view(points)
            self.map.get_map().go_to_full(lat, lon, zoom)

    def _popover(self, place: str, jobs: list[Job], parent: Gtk.Widget) -> Gtk.Popover:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=6, margin_bottom=6,
                        margin_start=6, margin_end=6)
        title = Gtk.Label(xalign=0, use_markup=True)
        title.set_markup(f"<b>{GLib.markup_escape_text(place)}</b>")
        outer.append(title)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        popover = Gtk.Popover()
        ranked = sorted(jobs, key=lambda job: (-(self._evaluations[job.key].score or 0)
                                                if job.key in self._evaluations else 0))
        for job in ranked[:LISTED]:
            evaluation = self._evaluations.get(job.key)
            fit = evaluation.fit.label if evaluation else Fit.UNKNOWN.label
            score = f" {round((evaluation.score or 0) * 100)} %" if evaluation and evaluation.score is not None else ""
            button = Gtk.Button(css_classes=["flat"], halign=Gtk.Align.FILL)
            mode = f" · {job.work_mode.label}" if job.work_mode is not WorkMode.UNKNOWN else ""
            label = Gtk.Label(label=f"{job.company} · {job.title}  ({fit}{score}{mode})", xalign=0, wrap=True,
                              max_width_chars=48)
            button.set_child(label)
            button.connect("clicked", lambda _button, j=job, p=popover: (p.popdown(), self._on_pick(j)))
            box.append(button)
        if len(jobs) > LISTED:
            box.append(Gtk.Label(label=_("y {count} más").format(count=len(jobs) - LISTED), xalign=0,
                                 css_classes=["dim-label"]))
        # Con muchas ofertas el contenido no cabe en el mapa y GTK no llega a mostrar el globo: se desplaza.
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                    max_content_height=POPOVER_HEIGHT)
        scroll.set_child(box)
        outer.append(scroll)
        popover.set_child(outer)
        popover.set_parent(parent)
        return popover
