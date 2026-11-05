"""La pestaña «Mercado»: tus radares frente a lo que piden, de media, las ofertas que estás viendo."""
from collections.abc import Callable
from threading import Thread

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..i18n import _
from ..market import Market, build_market, relevant_jobs
from ..models import Evaluation, Fit, Job
from ..profiles import Profile
from .radar_panel import RadarPanel

SOURCES = ("visible", "relevant")   # las que ves ahora / solo las de encaje alto o medio


def source_labels() -> list[str]:
    return [_("Las que veo ahora"), _("Solo encaje alto o medio")]


class MarketPage(Gtk.Box):
    """Un selector de qué ofertas cuentan y, debajo, los radares del perfil con la demanda media del mercado.

    `provider()` da lo que se ve ahora: las ofertas, sus evaluaciones y el perfil. Se calcula en segundo plano cuando se
    abre la pestaña (los filtros se cambian en la otra) y se vuelve a calcular solo si algo ha cambiado."""

    def __init__(self, provider: Callable[[], tuple[list[Job], dict[str, Evaluation], Profile | None]]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_start=8, margin_end=8)
        self._provider = provider
        self._token = 0
        self._key: tuple | None = None
        controls = Gtk.Box(spacing=8)
        controls.append(Gtk.Label(label=_("Ofertas")))
        self.source = Gtk.DropDown.new_from_strings(source_labels())
        self.source.connect("notify::selected", lambda *_args: self.refresh())
        controls.append(self.source)
        self.status = Gtk.Label(xalign=0, hexpand=True)
        self.status.add_css_class("dim-label")
        controls.append(self.status)
        self.append(controls)
        self.message = Gtk.Label(label=_("Elige un perfil para ver su mapa del mercado."), xalign=0, visible=False)
        self.append(self.message)
        self.panel = RadarPanel(vexpand=True)
        self.append(self.panel)

    def invalidate(self) -> None:
        """Los datos han cambiado: la próxima vez que se abra la pestaña se calcula de nuevo."""
        self._key = None

    def refresh(self) -> None:
        jobs, evaluations, profile = self._provider()
        if profile is None or not profile.name:
            self._key = None
            self._token += 1
            self.status.set_text("")
            self.message.set_visible(True)
            self.panel.set_visible(False)
            return
        self.message.set_visible(False)
        self.panel.set_visible(True)
        relevant = SOURCES[self.source.get_selected()] == "relevant"
        chosen = relevant_jobs(jobs, evaluations) if relevant else jobs
        key = (tuple(job.key for job in chosen), repr(profile.to_dict()), relevant)
        if key == self._key:
            return
        self._key = key
        self._token += 1
        token = self._token
        self.status.set_text(_("Calculando…"))

        def work() -> None:
            market = build_market(chosen, profile)
            GLib.idle_add(self._show, token, market)

        Thread(target=work, daemon=True).start()

    def _show(self, token: int, market: Market) -> bool:
        if token != self._token:
            return False   # se pidió otro cálculo mientras tanto
        self.status.set_text(
            _("{count} de {seen} ofertas con descripción completa").format(count=market.offers, seen=market.seen))
        self.panel.set_data(market.radars, Fit.UNKNOWN, market=market.offers)
        return False
