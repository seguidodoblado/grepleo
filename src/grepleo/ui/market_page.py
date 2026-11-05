"""La pestaña «Mercado»: tus radares frente a lo que piden, de media, las ofertas que estás viendo."""
from collections.abc import Callable
from threading import Thread

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, GObject, Gtk, Pango

from ..i18n import _
from ..market import Market, OfferRow, build_market, build_rows, low_fit_jobs, relevant_jobs
from ..models import Evaluation, Fit, Job
from ..profiles import Profile
from ..study import StudyItem, study_plan
from .common import wide_scrollbars
from .radar_minimap import overlap_class, percent
from .radar_panel import RadarPanel
from .study_links import study_button

FIT_TINT = {Fit.HIGH: "high", Fit.MEDIUM: "medium", Fit.LOW: "low"}   # el color de la celda de encaje
SOURCES = ("visible", "relevant", "low")   # las que ves ahora / solo encaje alto o medio / solo encaje bajo


class _RowItem(GObject.Object):
    """Una fila del desglose: la oferta con sus valores."""

    def __init__(self, row: OfferRow) -> None:
        super().__init__()
        self.row = row


def row_cells(row: OfferRow) -> list[tuple[str, str, float]]:
    """Las celdas de una fila: (texto, color de fondo, valor para ordenar), en el orden de las columnas (oferta, encaje,
    solape global y el de cada radar)."""
    score = f" {round(row.score * 100)} %" if row.score is not None else ""
    cells = [(f"{row.job.company} · {row.job.title}", "", 0.0),
             (f"{row.fit.label}{score}", FIT_TINT.get(row.fit, "none"), row.score if row.score is not None else -1.0)]
    for value in (row.overall, *row.overlaps):
        cells.append((percent(value), overlap_class(value), value if value is not None else -1.0))
    return cells


def _column(title: str, index: int, expand: bool = False) -> Gtk.ColumnViewColumn:
    """Una columna del desglose: se ordena al pulsar su cabecera y la cabecera no se mueve al bajar."""
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item) -> None:
        label = Gtk.Label(xalign=0 if index == 0 else 0.5, ellipsize=Pango.EllipsizeMode.END, max_width_chars=40)
        if index:
            label.add_css_class("radar-thumb")
        item.set_child(label)

    def bind(_factory, item) -> None:
        label = item.get_child()
        text, tint, _key = row_cells(item.get_item().row)[index]
        label.set_text(text)
        if index == 0:
            label.set_tooltip_text(item.get_item().row.job.title)
        for old in [name for name in label.get_css_classes() if name.startswith("radar-thumb-")]:
            label.remove_css_class(old)
        if tint:
            label.add_css_class(f"radar-thumb-{tint}")

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    column = Gtk.ColumnViewColumn(title=title, factory=factory, resizable=True, expand=expand)
    if index == 0:
        column.set_sorter(Gtk.CustomSorter.new(
            lambda a, b, _data: (a.row.job.company.casefold() > b.row.job.company.casefold())
            - (a.row.job.company.casefold() < b.row.job.company.casefold()), None))
    else:
        column.set_sorter(Gtk.CustomSorter.new(
            lambda a, b, _data: (row_cells(a.row)[index][2] > row_cells(b.row)[index][2])
            - (row_cells(a.row)[index][2] < row_cells(b.row)[index][2]), None))
    return column


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
        # un desplegable plegado no debe reclamar espacio: su contenido (con scroll) pide crecer y, aun oculto, hacía que
        # cada título dejara debajo un hueco en blanco; solo crece mientras está desplegado (`_toggle_expand`)
        self.plan = Gtk.Expander(label=_("Plan de estudio: lo que más conviene reforzar"), vexpand=False)
        self.plan.connect("notify::expanded", self._toggle_expand)
        self._plan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._plan_holder = wide_scrollbars(Gtk.ScrolledWindow(min_content_height=200, vexpand=True))
        self._plan_box.append(self._plan_holder)
        self.plan.set_child(self._plan_box)
        self.append(self.plan)
        self.breakdown = Gtk.Expander(label=_("Desglose por oferta"), margin_bottom=8, vexpand=False)
        self.breakdown.connect("notify::expanded", self._toggle_expand)
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
        self._show_plan(market)
        return False

    def _show_plan(self, market: Market) -> None:
        """El plan de estudio: lo que más piden las ofertas por encima de tu nivel, con certificaciones y cursos."""
        items = study_plan(market)
        self.plan.set_expanded(SOURCES[self.source.get_selected()] == "low" and bool(items))   # con el filtro de plan, abierto
        if not items:
            self._plan_holder.set_child(Gtk.Label(label=_("Con estas ofertas no hay nada que reforzar: tu nivel llega a "
                                                          "lo que piden."), xalign=0, margin_top=6, wrap=True))
            return
        grid = Gtk.Grid(column_spacing=12, row_spacing=4, margin_start=4, margin_end=8, margin_top=4)
        for column, text in enumerate((_("Habilidad"), _("Radar"), _("Tu nivel → lo que piden"), _("Ofertas"), "")):
            head = Gtk.Label(label=text, xalign=0)
            head.add_css_class("heading")
            grid.attach(head, column, 0, 1, 1)
        for number, item in enumerate(items, start=1):
            self._attach_plan_row(grid, number, item)
        self._plan_holder.set_child(grid)

    @staticmethod
    def _attach_plan_row(grid: Gtk.Grid, number: int, item: StudyItem) -> None:
        name = Gtk.Label(xalign=0)
        name.set_markup(f"<b>{GLib.markup_escape_text(item.name)}</b>")
        grid.attach(name, 0, number, 1, 1)
        grid.attach(Gtk.Label(label=item.radar, xalign=0), 1, number, 1, 1)
        grid.attach(Gtk.Label(label=f"{item.level:.0f} → {item.demand:.0f}", xalign=0), 2, number, 1, 1)
        grid.attach(Gtk.Label(label=_("el {share} %").format(share=round(100 * item.share)), xalign=0), 3, number, 1, 1)
        grid.attach(study_button(item.name), 4, number, 1, 1)

    @staticmethod
    def _toggle_expand(expander: Gtk.Expander, _param) -> None:
        expander.set_vexpand(expander.get_expanded())

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
        store = Gio.ListStore.new(_RowItem)
        for row in rows:
            store.append(_RowItem(row))
        # una ColumnView: su cabecera se queda fija al bajar y las columnas siguen alineadas con ella; cada columna se ordena
        view = Gtk.ColumnView(show_row_separators=True, single_click_activate=True)
        columns = [_column(_("Oferta"), 0, expand=True)]
        columns += [_column(title, index) for index, title in
                    enumerate((_("Encaje"), _("Solape global"), *titles), start=1)]
        for column in columns:
            view.append_column(column)
        sort_model = Gtk.SortListModel(model=store, sorter=view.get_sorter())
        view.set_model(Gtk.NoSelection(model=sort_model))
        view.connect("activate", lambda _view, position: self._on_pick(sort_model.get_item(position).row.job))
        view.sort_by_column(columns[2], Gtk.SortType.DESCENDING)   # de la que más cubres a la que menos
        self._rows_view, self._rows_store = view, store
        self._grid_holder.set_child(view)
        return False
