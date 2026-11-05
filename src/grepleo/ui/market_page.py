"""La pestaña «Mercado»: tus radares frente a lo que piden, de media, las ofertas que estás viendo."""
from collections.abc import Callable
from threading import Thread

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..i18n import _
from ..market import Market, OfferRow, build_market, build_rows, low_fit_jobs, relevant_jobs
from ..models import Evaluation, Fit, Job
from ..profiles import Profile
from .common import wide_scrollbars
from .radar_minimap import overlap_class, percent
from .radar_panel import RadarPanel

FIT_TINT = {Fit.HIGH: "high", Fit.MEDIUM: "medium", Fit.LOW: "low"}   # el color de la celda de encaje
SOURCES = ("visible", "relevant", "low")   # las que ves ahora / solo encaje alto o medio / solo encaje bajo


def source_labels() -> list[str]:
    return [_("Las que veo ahora"), _("Solo encaje alto o medio"), _("Solo encaje bajo (plan de estudio)")]


class MarketPage(Gtk.Box):
    """Un selector de qué ofertas cuentan (las que ves, solo las de encaje alto o medio, o solo las de encaje bajo: lo que
    te falta, como plan de estudio) y, debajo, los radares del perfil con la demanda media del mercado.

    `provider()` da lo que se ve ahora: las ofertas, sus evaluaciones y el perfil. Se calcula en segundo plano cuando se
    abre la pestaña (los filtros se cambian en la otra) y se vuelve a calcular solo si algo ha cambiado."""

    def __init__(self, provider: Callable[[], tuple[list[Job], dict[str, Evaluation], Profile | None]],
                 on_pick: Callable[[Job], None] = lambda _job: None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_start=8, margin_end=8)
        self._provider = provider
        self._on_pick = on_pick
        self._chosen: list[Job] = []
        self._evaluations: dict[str, Evaluation] = {}
        self._profile: Profile | None = None
        self._market: Market | None = None
        self._rows_key: tuple | None = None
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
        self.breakdown = Gtk.Expander(label=_("Desglose por oferta"), margin_bottom=8)
        self.breakdown.connect("notify::expanded", self._breakdown_toggled)
        self._rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._rows_status = Gtk.Label(xalign=0)
        self._rows_status.add_css_class("dim-label")
        self._rows_box.append(self._rows_status)
        self._grid_holder = wide_scrollbars(Gtk.ScrolledWindow(min_content_height=240, vexpand=True))
        self._rows_box.append(self._grid_holder)
        self.breakdown.set_child(self._rows_box)
        self.append(self.breakdown)

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
        which = SOURCES[self.source.get_selected()]
        chosen = (relevant_jobs(jobs, evaluations) if which == "relevant"
                  else low_fit_jobs(jobs, evaluations) if which == "low" else jobs)
        key = (tuple(job.key for job in chosen), repr(profile.to_dict()), which)
        if key == self._key:
            return
        self._key = key
        self._chosen, self._evaluations, self._profile = chosen, evaluations, profile
        self._rows_key = None   # el desglose es de otras ofertas: se vuelve a calcular al abrirlo
        self._token += 1
        token = self._token
        self.status.set_text(_("Calculando…"))
        if self.breakdown.get_expanded():
            self._load_rows()

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
        self._market = market
        return False

    # --- el desglose por oferta -----------------------------------------------------------------
    def _breakdown_toggled(self, *_args) -> None:
        if self.breakdown.get_expanded():
            self._load_rows()

    def _load_rows(self) -> None:
        """Calcula, al abrirlo, lo que cubres de cada oferta en cada radar (en segundo plano)."""
        if self._profile is None or self._key is None or self._rows_key == self._key:
            return
        key, chosen, evaluations, profile = self._key, self._chosen, self._evaluations, self._profile
        self._rows_status.set_text(_("Calculando…"))

        def work() -> None:
            rows = build_rows(chosen, evaluations, profile)
            GLib.idle_add(self._show_rows, key, rows)

        Thread(target=work, daemon=True).start()

    def _show_rows(self, key: tuple, rows: list[OfferRow]) -> bool:
        if key != self._key:
            return False   # los datos han cambiado mientras tanto
        self._rows_key = key
        titles = [radar.title for radar in self._market.radars] if self._market is not None else []
        self._rows_status.set_text(_("{count} ofertas, de la que más cubres a la que menos").format(count=len(rows)))
        grid = Gtk.Grid(column_spacing=8, row_spacing=3, margin_start=4, margin_end=8, margin_top=4)
        headers = [_("Oferta"), _("Encaje"), _("Solape global"), *titles]
        for column, text in enumerate(headers):
            head = Gtk.Label(label=text, xalign=0 if column == 0 else 0.5, ellipsize=3, max_width_chars=12 if column else 40)
            head.add_css_class("heading")
            head.set_tooltip_text(text)
            grid.attach(head, column, 0, 1, 1)
        for number, row in enumerate(rows, start=1):
            button = Gtk.Button(css_classes=["flat"], halign=Gtk.Align.FILL, tooltip_text=row.job.title)
            button.set_child(Gtk.Label(label=f"{row.job.company} · {row.job.title}", xalign=0, ellipsize=3, max_width_chars=40))
            button.connect("clicked", lambda _button, job=row.job: self._on_pick(job))
            grid.attach(button, 0, number, 1, 1)
            score = f" {round(row.score * 100)} %" if row.score is not None else ""
            fit = Gtk.Label(label=f"{row.fit.label}{score}")
            fit.add_css_class(f"radar-thumb-{FIT_TINT.get(row.fit, 'none')}")
            fit.add_css_class("radar-thumb")
            grid.attach(fit, 1, number, 1, 1)
            for column, value in enumerate((row.overall, *row.overlaps), start=2):
                cell = Gtk.Label(label=percent(value))
                cell.add_css_class("radar-thumb")
                cell.add_css_class(f"radar-thumb-{overlap_class(value)}")
                grid.attach(cell, column, number, 1, 1)
        self._grid_holder.set_child(grid)
        return False
