"""Ventana principal: búsqueda, resultados con su encaje, detalle de criterios, panorama y exportación."""
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from .. import __version__, settings
from .. import secrets as token_store
from ..assistant import build_argv, build_prompt, prepare_workspace
from ..ats import LIKELY, POSSIBLE, AtsEstimate, estimate_ats
from ..gaps import Gap, Strength, find_gaps, find_strengths
from ..i18n import _, ngettext
from ..incremental import incremental_posted, prune_stale, same_search
from ..matching import evaluate
from ..models import Evaluation, Fit, Job, JobState, Stage, WorkMode
from ..panorama import build_panorama
from ..profiles import Profile
from ..radar import build_radars
from ..report import export_csv, export_html
from ..sources import POSTED, SOURCES, SearchQuery, plan_search, run_search
from ..storage import DATA_DIR, SavedSearch, Store
from ..textutil import normalize
from .assistant_window import AssistantWindow
from .common import (
    APPEARANCE,
    ask_text,
    confirm,
    icon_button,
    install_css,
    labeled,
    message,
    pick_icon,
    source_icon,
    vte_available,
    wide_scrollbars,
)
from .date_picker import today
from .detail_view import DetailView
from .map_page import MapPage
from .market_page import MarketPage
from .notes_panel import NotesPanel
from .profile_dialog import ProfileWindow
from .radar_panel import RadarPanel
from .study_links import study_button
from .theming import is_dark_theme, theme_variant
from .tracking_panel import TrackingPanel

AUTHOR = "Jose Antonio Seguido Doblado"
AUTHOR_EMAIL = "jose.antonio.seguido@gmail.com"
REPO_URL = "https://github.com/seguidodoblado/grepleo"
LAST_SEARCH = "·última·"          # nombre reservado de la búsqueda que se guarda sola
CONFIRM_ABOVE_USD = 0.25          # por encima de este coste estimado se pide confirmación
STATE_ICONS = {   # nombres del tema, del preferido al de reserva
    JobState.NEW: ("media-record", "emblem-new", "mail-unread", "dialog-information"),   # un punto, como «sin leer»
    JobState.FAVORITE: ("starred", "emblem-favorite", "non-starred"),
    JobState.APPLIED: ("mail-send", "emblem-default", "object-select"),
    JobState.DISCARDED: ("user-trash", "edit-delete", "process-stop"),
}
STATE_FILTERS = ("active", "all", "favorite", "applied", "discarded", "process", "notes")
NOTES_ICONS = {"due": ("alarm", "appointment-soon", "dialog-warning"), "notes": ("document-edit", "text-x-generic")}
FIT_FILTERS = (None, Fit.HIGH, Fit.MEDIUM, Fit.LOW, Fit.UNKNOWN)
MODE_FILTERS = (None, WorkMode.REMOTE, WorkMode.HYBRID, WorkMode.ONSITE, WorkMode.UNKNOWN)
ATS_FILTERS = (None, (LIKELY, 101), (POSSIBLE, LIKELY), (0, POSSIBLE))   # rangos [desde, hasta) de la estimación
ATS_CHUNK = 12                    # ofertas que se calculan por tanda, para no bloquear la ventana


def posted_labels() -> list[str]:
    return [_("Cualquier fecha"), _("Últimas 24 horas"), _("Última semana"), _("Último mes")]


def state_filter_labels() -> list[str]:
    return [_("Candidatas"), _("Todas"), _("Favoritas"), _("Postuladas"), _("Descartadas"),
            _("Proceso abierto"), _("Con notas o seguimiento")]


def ats_filter_labels() -> list[str]:
    return [_("ATS: todas"), _("Probable (≥ {percent} %)").format(percent=LIKELY),
            _("Posible ({low}–{high} %)").format(low=POSSIBLE, high=LIKELY - 1),
            _("Poco probable (< {percent} %)").format(percent=POSSIBLE)]


def mode_filter_labels() -> list[str]:
    return [_("Modalidad: todas"), WorkMode.REMOTE.label, WorkMode.HYBRID.label, WorkMode.ONSITE.label,
            _("Sin indicar")]


def fit_filter_labels() -> list[str]:
    return [_("Encaje: todos"), _("Alto"), _("Medio"), _("Bajo"), _("Sin datos")]


def source_names() -> dict[str, str]:
    return {source_id: source.name for source_id, source in SOURCES.items()}


def duplicate_key(job: Job) -> str:
    """Dos ofertas con la misma empresa, puesto y ubicación son la misma aunque vengan de fuentes distintas."""
    return "|".join(normalize(part) for part in (job.company, job.title, job.location))


def merge_jobs(jobs: list[Job]) -> list[Job]:
    """Quita los duplicados entre fuentes, prefiriendo la oferta con descripción completa."""
    chosen: dict[str, Job] = {}
    for job in jobs:
        key = duplicate_key(job)
        current = chosen.get(key)
        if current is None or (job.full_description and not current.full_description):
            chosen[key] = job
    return list(chosen.values())


class JobItem(GObject.Object):
    """Una fila de la tabla: la oferta, su evaluación y, cuando se ha calculado, su estimación ATS."""

    ats_percent = GObject.Property(type=int, default=-1)   # -1: aún sin calcular; al cambiar avisa a su celda

    def __init__(self, job: Job, evaluation: Evaluation) -> None:
        super().__init__()
        self.job = job
        self.evaluation = evaluation
        self.ats: AtsEstimate | None = None

    def set_ats(self, estimate: AtsEstimate) -> None:
        self.ats = estimate
        self.ats_percent = estimate.percent


def ats_text(item: "JobItem") -> str:
    return "…" if item.ats_percent < 0 else f"{item.ats_percent} %"


def ats_tooltip(item: "JobItem") -> str:
    if item.ats is None:
        return _("Calculando la compatibilidad ATS…")
    return f"{item.ats.verdict}\n" + _("fiabilidad {level}").format(level=item.ats.reliability_label)


def fit_text(item: "JobItem") -> str:
    """El encaje y su puntuación ponderada (la que ordena la columna)."""
    score = item.evaluation.score
    return f"{item.evaluation.fit.label}\n{round(score * 100)} %" if score is not None else item.evaluation.fit.label


def fit_tooltip(item: "JobItem") -> str:
    """Qué significa el porcentaje, cuántos criterios se cumplen y qué es lo que más falta."""
    text = _("Puntuación ponderada: cada criterio pesa distinto.\nCumples {count} criterios (los «no se sabe» no cuentan).").format(
        count=item.evaluation.summary)
    gaps = item.evaluation.main_gaps()
    if gaps:
        text += "\n" + _("Te falta: {names}").format(names=", ".join(gaps))
    return text


def _demand_text(offers: int, required: int, relevant: int) -> str:
    detail = ngettext("la pide {count} oferta", "la piden {count} ofertas", offers).format(count=offers)
    extra = []
    if required:
        extra.append(_("{count} como requisito").format(count=required))
    if relevant:
        extra.append(_("{count} de encaje alto o medio").format(count=relevant))
    return detail + (f" ({', '.join(extra)})" if extra else "")


def gap_text(gap: Gap) -> str:
    """Una línea por hueco: qué te falta y cuántas ofertas lo piden."""
    head = gap.how[:1].upper() + gap.how[1:]   # «no la tienes», «tienes algo parecido: AWS», «tu nivel: 2 de 10»…
    return f"{head} · {_demand_text(gap.offers, gap.required, gap.relevant)}"


def strength_text(strength: Strength) -> str:
    """Una línea por punto fuerte: lo que ya tienes y cuántas ofertas lo piden."""
    head = _("Tu nivel: {level} de 10").format(level=strength.level) if strength.level is not None else _("En tu perfil")
    return f"{head} · {_demand_text(strength.offers, strength.required, strength.relevant)}"


def state_icon_of(item: JobItem) -> str:
    """El icono del estado de una oferta ('' si es nueva)."""
    names = STATE_ICONS.get(item.job.state)
    return pick_icon(*names) if names else ""


def stage_of(job: Job) -> Stage:
    try:
        return Stage(job.stage)
    except ValueError:
        return Stage.NONE


def state_text(job: Job) -> str:
    """El estado de la oferta y, debajo, la fase de su proceso de selección si la hay."""
    stage = stage_of(job)
    return job.state.label + (f"\n{stage.label}" if stage is not Stage.NONE else "")


def notes_mark(job: Job, day: str) -> str:
    """«due» si el recordatorio vence hoy o antes, «notes» si hay algo apuntado, '' si nada."""
    if job.remind_on and job.remind_on <= day:
        return "due"
    return "notes" if job.has_tracking else ""


def notes_icon_of(item: "JobItem") -> str:
    mark = notes_mark(item.job, today().isoformat())
    return pick_icon(*NOTES_ICONS[mark]) if mark else ""


def notes_tooltip(job: Job) -> str:
    lines = [job.notes.splitlines()[0][:120]] if job.notes else []
    if stage_of(job) is not Stage.NONE:
        lines.append(_("Fase: {stage}").format(stage=stage_of(job).label))
    if job.next_steps:
        lines.append(_("Próximos pasos: {steps}").format(steps=job.next_steps.splitlines()[0][:100]))
    if job.event_count:
        lines.append(ngettext("{count} anotación en el histórico", "{count} anotaciones en el histórico",
                              job.event_count).format(count=job.event_count))
    if job.remind_on:
        lines.append(_("Recordatorio: {date}").format(date=job.remind_on))
    return "\n".join(lines)


def criteria_text(evaluation: Evaluation) -> str:
    return "  ".join(f"{item.status.symbol} {item.name}" for item in evaluation.criteria)


def salary_text(job: Job) -> str:
    return (job.salary_text or "—") + (" " + _("(est.)") if job.salary_estimated and job.salary_text else "")


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, store: Store) -> None:
        super().__init__(application=app, title="Grepleo")
        self.set_default_size(1280, 820)
        self.store = store
        self.profiles: list[tuple[int, Profile]] = []
        self.saved_searches: list[SavedSearch] = []
        self.last_search_id: int | None = None
        self.current_search_id: int | None = None
        self.jobs: list[Job] = []
        self.evaluations: dict[str, Evaluation] = {}
        self.searching = False
        self._updating = False
        self._row_signatures: dict[str, tuple[str, str]] = {}
        self._ats_cache: dict[tuple[str, str], AtsEstimate] = {}
        self._ats_profile_key = ""
        self._ats_generation = 0

        header = Gtk.HeaderBar()
        header.pack_end(self._build_menu_button())
        header.pack_end(self._build_export_button())
        self.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12, margin_bottom=12,
                       margin_start=12, margin_end=12)
        root.append(self._build_search_area())
        self.notebook = Gtk.Notebook(vexpand=True)
        self.notebook.append_page(self._build_results_page(), Gtk.Label(label=_("Ofertas")))
        self.notebook.append_page(self._build_panorama_page(), Gtk.Label(label=_("Panorama")))
        self.market = MarketPage(self._market_data, self._pick_job)
        self.notebook.append_page(self.market, Gtk.Label(label=_("Mercado")))
        self.map_page = MapPage(self._market_data, self.store, self._pick_job, dark=APPEARANCE.dark)
        self.notebook.append_page(self.map_page, Gtk.Label(label=_("Mapa")))
        self.notebook.connect("switch-page", self._on_main_tab)
        root.append(self.notebook)
        self.status = Gtk.Label(xalign=0, wrap=True)
        root.append(self.status)
        self.set_child(root)

        self._reload_profiles()
        self._reload_searches()
        self._load_last_search()
        self._update_estimate()
        if not self.profiles:
            self.status.set_text(_("Crea un perfil con tus criterios para ver qué ofertas encajan contigo."))
        self._announce_reminders()
        self.connect("close-request", self._flush_notes)

    def _flush_notes(self, *_args) -> bool:
        self.notes_panel.flush()   # lo escrito en los últimos instantes
        self.tracking_panel.flush()
        for window in getattr(self, "_assistant_windows", []):   # que no quede una sesión de IA abierta sin ventana madre
            if window.is_visible():
                window.close()
            window.shutdown()   # incluso las ocultas que esperaban a que su CLI terminara: la aplicación se va ya
        return False

    # --- construcción ------------------------------------------------------------------------------
    def _build_menu_button(self) -> Gtk.MenuButton:
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_start=6, margin_end=6,
                      margin_top=6, margin_bottom=6)
        entries = ((_("Preferencias"), ("preferences-system",), self._open_preferences),
                   (_("Acerca de Grepleo"), ("help-about",), self._open_about))
        for label, icons, callback in entries:
            item = icon_button(icons, label, halign=Gtk.Align.FILL)
            item.connect("clicked", lambda _button, fn=callback: (popover.popdown(), fn()))
            box.append(item)
        popover.set_child(box)
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text=_("Menú principal"))
        menu.set_popover(popover)
        return menu

    def _build_export_button(self) -> Gtk.MenuButton:
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_start=6, margin_end=6,
                      margin_top=6, margin_bottom=6)
        for label, kind in ((_("Informe HTML…"), "html"), (_("Tabla CSV…"), "csv")):
            item = icon_button(("document-save",), label, halign=Gtk.Align.FILL)
            item.connect("clicked", lambda _button, k=kind: (popover.popdown(), self._export(k)))
            box.append(item)
        popover.set_child(box)
        button = Gtk.MenuButton(label=_("Exportar"), tooltip_text=_("Exporta las ofertas que se ven ahora"))
        button.set_popover(popover)
        return button

    def _build_search_area(self) -> Gtk.Box:
        area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        profile_row = Gtk.Box(spacing=8)
        self.profile_drop = Gtk.DropDown.new_from_strings([""])
        self.profile_drop.set_hexpand(True)
        self.profile_drop.connect("notify::selected", self._on_profile_changed)
        profile_row.append(labeled(_("Perfil"), self.profile_drop))
        for icons, text, handler in ((("list-add",), _("Nuevo"), self._new_profile),
                                     (("document-edit",), _("Editar"), self._edit_profile),
                                     (("edit-delete",), _("Borrar"), self._delete_profile)):
            button = icon_button(icons, text, valign=Gtk.Align.END)
            button.connect("clicked", handler)
            profile_row.append(button)
        self.search_drop = Gtk.DropDown.new_from_strings([""])
        self.search_drop.set_hexpand(True)
        self.search_drop.connect("notify::selected", self._on_saved_search_chosen)
        profile_row.append(labeled(_("Búsquedas guardadas"), self.search_drop))
        save = icon_button(("document-save",), _("Guardar"), valign=Gtk.Align.END)
        save.connect("clicked", self._save_search)
        remove = icon_button(("edit-delete",), _("Borrar"), valign=Gtk.Align.END)
        remove.connect("clicked", self._delete_search)
        profile_row.append(save)
        profile_row.append(remove)
        area.append(profile_row)

        query_row = Gtk.Box(spacing=8)
        self.keywords = Gtk.Entry(hexpand=True, placeholder_text=_("Por ejemplo: product owner"), activates_default=True)
        self.keywords.connect("activate", self._start_search)
        query_row.append(labeled(_("Puesto o palabras clave"), self.keywords))
        self.location = Gtk.Entry(placeholder_text=_("Madrid"), width_chars=18)
        query_row.append(labeled(_("Ubicación"), self.location))
        self.limit = Gtk.SpinButton.new_with_range(5, 500, 5)
        self.limit.set_value(50)
        self.limit.connect("value-changed", lambda *_args: self._update_estimate())
        query_row.append(labeled(_("Ofertas por fuente"), self.limit))
        self.posted = Gtk.DropDown.new_from_strings(posted_labels())
        query_row.append(labeled(_("Publicadas"), self.posted))
        self.remote = Gtk.CheckButton(label=_("Solo remoto"), valign=Gtk.Align.END)
        query_row.append(self.remote)
        self.incremental = Gtk.CheckButton(label=_("Solo novedades"), active=True, valign=Gtk.Align.END)
        self.incremental.set_tooltip_text(_("Si repites una búsqueda, pide solo lo publicado desde la última vez y "
                                            "lo suma a lo que ya tienes: gasta menos en Apify."))
        self.incremental.connect("toggled", lambda *_args: self._update_estimate())
        query_row.append(self.incremental)
        area.append(query_row)

        action_row = Gtk.Box(spacing=12)
        self.source_checks: dict[str, Gtk.CheckButton] = {}
        for source_id, source in SOURCES.items():
            check = Gtk.CheckButton(active=True)
            content = Gtk.Box(spacing=6)
            content.append(Gtk.Image(icon_name=source_icon(source_id)))
            content.append(Gtk.Label(label=source.name))
            check.set_child(content)
            check.connect("toggled", lambda *_args: self._update_estimate())
            self.source_checks[source_id] = check
            action_row.append(check)
        # con puntos suspensivos si no cabe: un texto largo no debe ensanchar el mínimo de la ventana
        self.estimate = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self.estimate.add_css_class("dim-label")
        action_row.append(self.estimate)
        self.spinner = Gtk.Spinner()
        action_row.append(self.spinner)
        self.search_button = icon_button(("system-search", "edit-find"), _("Buscar"))
        self.search_button.add_css_class("suggested-action")
        self.search_button.connect("clicked", self._start_search)
        action_row.append(self.search_button)
        area.append(action_row)
        return area

    def _build_results_page(self) -> Gtk.Box:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8)
        filters = Gtk.Box(spacing=8)
        self.filter_text = Gtk.SearchEntry(hexpand=True, placeholder_text=_("Buscar empresa, puesto o requisito"))
        self.filter_text.connect("search-changed", lambda *_args: self._filters_changed())
        filters.append(self.filter_text)
        self.filter_fit = Gtk.DropDown.new_from_strings(fit_filter_labels())
        self.filter_fit.connect("notify::selected", lambda *_args: self._filters_changed())
        filters.append(self.filter_fit)
        self.filter_mode = Gtk.DropDown.new_from_strings(mode_filter_labels())
        self.filter_mode.set_tooltip_text(_("Filtra las ofertas ya encontradas por modalidad de trabajo"))
        self.filter_mode.connect("notify::selected", lambda *_args: self._filters_changed())
        filters.append(self.filter_mode)
        self.filter_ats = Gtk.DropDown.new_from_strings(ats_filter_labels())
        self.filter_ats.set_tooltip_text(_("Filtra por la compatibilidad ATS estimada: lo que tu CV tiene de pasar el filtro "
                                           "automático de la empresa"))
        self.filter_ats.connect("notify::selected", lambda *_args: self._filters_changed())
        filters.append(self.filter_ats)
        self.filter_category = Gtk.DropDown.new_from_strings([_("Tipo: todos")])
        self.filter_category.connect("notify::selected", lambda *_args: self._filters_changed())
        filters.append(self.filter_category)
        self.filter_state = Gtk.DropDown.new_from_strings(state_filter_labels())
        self.filter_state.connect("notify::selected", lambda *_args: self._filters_changed())
        filters.append(self.filter_state)
        self.counter = Gtk.Label()
        self.counter.add_css_class("dim-label")
        filters.append(self.counter)
        page.append(filters)

        self.store_model = Gio.ListStore.new(JobItem)
        self.filter = Gtk.CustomFilter.new(self._item_matches)
        self.filter_model = Gtk.FilterListModel(model=self.store_model, filter=self.filter)
        self.view = Gtk.ColumnView(vexpand=True, show_row_separators=True)
        self.sort_model = Gtk.SortListModel(model=self.filter_model, sorter=self.view.get_sorter())
        self.selection = Gtk.SingleSelection(model=self.sort_model)
        self.view.set_model(self.selection)
        self.selection.connect("notify::selected-item", self._on_selection_changed)
        self.filter_model.connect("items-changed", lambda *_args: self._update_counter())

        # la tabla se queda con lo que sirve para escanear; el resto (criterios, experiencia, tipo…) va al panel
        columns = (
            (_("Empresa · Puesto"), lambda item: f"{item.job.company or '—'}\n{item.job.title}", 240, "company"),
            (_("Ubicación"), lambda item: f"{item.job.location or '—'}\n{item.job.work_mode.label}", 120, "location"),
            (_("Salario"), lambda item: salary_text(item.job), 110, "salary"),
            (_("Encaje"), fit_text, 80, "fit"),
            (_("ATS"), ats_text, 64, "ats"),   # se rellena en segundo plano; el icono de la estimación va en el tooltip
            (_("Estado"), lambda item: state_text(item.job), 130, "state"),
            (_("Notas"), lambda item: "", 64, "notes"),   # solo el icono; el texto sale al pasar el ratón
            (_("Fuente"), lambda item: "", 76, "source"),   # solo el icono; el nombre sale al pasar el ratón
        )
        self.fit_column = None
        for title, getter, width, sort_key in columns:
            icon = {"state": state_icon_of, "source": lambda item: source_icon(item.job.source),
                    "notes": notes_icon_of}.get(sort_key)
            # al agrandar la ventana, el espacio extra se reparte entre empresa y ubicación
            column = self._text_column(title, getter, width, sort_key, icon_getter=icon,
                                       expand=sort_key in ("company", "location"))
            self.view.append_column(column)
            if sort_key == "fit":
                self.fit_column = column
        self._sort_by_fit()

        scroll = wide_scrollbars(Gtk.ScrolledWindow(vexpand=True, min_content_width=560, min_content_height=280))
        scroll.set_child(self.view)
        self.detail = self._build_detail()
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True, shrink_start_child=False,
                          shrink_end_child=False)
        paned.set_start_child(scroll)
        paned.set_end_child(self.detail)
        paned.set_position(760)
        page.append(paned)
        return page

    def _sort_by_fit(self) -> None:
        """El orden predeterminado: de mejor a peor encaje."""
        if self.fit_column is not None:
            self.view.sort_by_column(self.fit_column, Gtk.SortType.DESCENDING)

    def _text_column(self, title, getter, width, sort_key, icon_getter=None, expand=False) -> Gtk.ColumnViewColumn:
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, row):
            box = Gtk.Box(spacing=6, margin_top=4, margin_bottom=4, margin_start=6, margin_end=6,
                          valign=Gtk.Align.START)
            box.append(Gtk.Image())
            box.append(Gtk.Label(xalign=0, wrap=True, max_width_chars=70))
            row.set_child(box)

        def bind(_factory, row):
            box = row.get_child()
            item = row.get_item()
            image, label = box.get_first_child(), box.get_last_child()
            text = getter(item)
            label.set_text(text)
            label.set_visible(bool(text))   # una columna solo de icono no deja hueco para el texto
            if sort_key == "ats":   # el cálculo es en segundo plano: la celda se actualiza cuando llega
                item.ats_handler = item.connect("notify::ats-percent", lambda *_args, i=item, lb=label: (
                    lb.set_text(ats_text(i)), box.set_tooltip_text(ats_tooltip(i))))
            tooltip = {"source": lambda: source_names().get(item.job.source, ""),
                       "notes": lambda: notes_tooltip(item.job),
                       "ats": lambda: ats_tooltip(item),
                       "fit": lambda: fit_tooltip(item)}.get(sort_key)
            box.set_tooltip_text(tooltip() or None if tooltip else None)
            icon = icon_getter(item) if icon_getter else ""
            image.set_visible(bool(icon))
            if icon:
                image.set_from_icon_name(icon)
            # toda la fila lleva el color del encaje: cada celda pinta su fondo
            cell = box.get_parent() or box
            for fit in Fit:
                cell.remove_css_class(f"row-fit-{fit.value}")
            cell.add_css_class(f"row-fit-{item.evaluation.fit.value}")

        def unbind(_factory, row):
            item = row.get_item()
            handler = getattr(item, "ats_handler", 0) if item is not None else 0
            if handler:
                item.disconnect(handler)
                item.ats_handler = 0

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        factory.connect("unbind", unbind)
        column = Gtk.ColumnViewColumn.new(title, factory)
        column.set_resizable(True)
        column.set_fixed_width(width)   # ancho mínimo; con expand=True crece con la ventana
        column.set_expand(expand)
        if sort_key:
            column.set_sorter(Gtk.CustomSorter.new(self._sorter_for(sort_key)))
        return column

    @staticmethod
    def _sorter_for(key):
        def value(item):
            if key == "fit":
                return (item.evaluation.fit.rank, item.evaluation.score or 0.0)
            if key == "ats":
                return item.ats_percent
            if key == "salary":
                top = item.job.salary_max if item.job.salary_max is not None else item.job.salary_min
                return (top is not None, top or 0.0)
            mapping = {"company": item.job.company, "category": item.evaluation.category,
                       "location": item.job.location, "experience": item.job.experience_text,
                       "state": item.job.state.value, "source": item.job.source,
                       "notes": {"due": "2", "notes": "1"}.get(notes_mark(item.job, today().isoformat()), "0")}
            return normalize(mapping.get(key, ""))

        def compare(first, second, *_extra):
            a, b = value(first), value(second)
            return (a > b) - (a < b)

        return compare

    def _build_detail(self) -> Gtk.Box:
        """El panel lateral: los botones siempre a la vista arriba y, debajo, los criterios y la descripción."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=10, margin_end=4)
        box.set_size_request(380, -1)
        # al menos dos botones por línea: con uno solo, a ancho mínimo se apilarían los cinco y el panel exigiría mucha altura
        buttons = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=2, max_children_per_line=4,
                              column_spacing=6, row_spacing=6, homogeneous=False)
        self.open_button = icon_button(("web-browser", "applications-internet"), _("Abrir oferta"))
        self.open_button.connect("clicked", self._open_job)
        buttons.append(self.open_button)
        self.cv_button = icon_button(("utilities-terminal", "document-edit", "text-x-generic"), _("Adaptar CV"))
        self.cv_button.set_tooltip_text(_("Abre un terminal con tu propia IA (Claude Code, OpenCode, Codex…) para "
                                          "adaptar tu currículum a esta oferta"))
        self.cv_button.connect("clicked", self._adapt_cv)
        buttons.append(self.cv_button)
        self.state_buttons: dict[JobState, Gtk.Button] = {}
        for state, text in ((JobState.FAVORITE, _("Favorita")), (JobState.APPLIED, _("Postulada")),
                            (JobState.DISCARDED, _("Descartar"))):
            button = icon_button(STATE_ICONS[state], text)
            button.connect("clicked", lambda _button, s=state: self._toggle_state(s))
            self.state_buttons[state] = button
            buttons.append(button)
        box.append(buttons)
        self.radar = RadarPanel(vexpand=True)
        self.detail_view = DetailView()
        detail_scroll = wide_scrollbars(Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        detail_scroll.set_child(self.detail_view)
        self.tracking_panel = TrackingPanel(self.store, self._tracking_changed)
        self.notes_panel = NotesPanel(self._notes_changed)
        # pestañas: la oferta, el radar, el seguimiento del proceso y las notas
        self.detail_tabs = Gtk.Notebook(vexpand=True, scrollable=True)
        # cada pestaña con su propio scroll: así el panel puede encogerse y no fija la altura mínima de la ventana
        tracking_scroll = wide_scrollbars(Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        tracking_scroll.set_child(self.tracking_panel)
        self._tab_pages = {"offer": detail_scroll, "radar": self.radar, "tracking": tracking_scroll,
                           "notes": self.notes_panel}
        for key in self._tab_pages:
            self.detail_tabs.append_page(self._tab_pages[key], Gtk.Label(label=self._tab_title(key)))
        self.detail_tabs.set_current_page(min(settings.detail_tab(), len(self._tab_pages) - 1))
        self.detail_tabs.connect("switch-page", lambda _notebook, _page, number: settings.set_detail_tab(number))
        box.append(self.detail_tabs)
        self._set_detail(None)
        return box

    @staticmethod
    def _tab_title(key: str, marked: bool = False) -> str:
        titles = {"offer": _("Oferta"), "radar": _("Radar"), "tracking": _("Seguimiento"), "notes": _("Notas")}
        return titles[key] + (" •" if marked else "")

    def _mark_tabs(self, job: Job | None) -> None:
        """Un punto en «Seguimiento» y «Notas» avisa de que esa oferta tiene algo apuntado."""
        marks = {"tracking": bool(job and (job.stage or job.next_steps or job.remind_on or job.event_count)),
                 "notes": bool(job and job.notes)}
        for key, marked in marks.items():
            self.detail_tabs.set_tab_label_text(self._tab_pages[key], self._tab_title(key, marked))

    def _market_data(self) -> tuple[list[Job], dict[str, Evaluation], Profile | None]:
        """Lo que alimenta la pestaña «Mercado»: las ofertas que pasan los filtros, sus evaluaciones y el perfil."""
        jobs = [self.filter_model.get_item(index).job for index in range(self.filter_model.get_n_items())]
        return jobs, self.evaluations, self._current_profile()

    def _on_main_tab(self, _notebook, page, _number) -> None:
        if page is self.market:
            GLib.idle_add(self.market.refresh)   # cuando la pestaña ya se ve, sin retrasar el cambio
        elif page is self.map_page:
            GLib.idle_add(self.map_page.refresh)

    def _pick_job(self, job: Job) -> None:
        """Desde el mapa: vuelve a la lista y elige esa oferta."""
        self.notebook.set_current_page(0)
        for position in range(self.selection.get_n_items()):
            item = self.selection.get_item(position)
            if item is not None and item.job is job:
                self.selection.set_selected(position)
                self.view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS, None)
                break

    def _build_panorama_page(self) -> Gtk.ScrolledWindow:
        self.panorama_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                                    margin_bottom=12, margin_start=12, margin_end=12)
        scroll = wide_scrollbars(Gtk.ScrolledWindow(vexpand=True))
        scroll.set_child(self.panorama_box)
        return scroll

    # --- perfiles ---------------------------------------------------------------------------------
    def _reload_profiles(self, select_id: int | None = None) -> None:
        previous = select_id if select_id is not None else self._current_profile_id()
        self.profiles = self.store.list_profiles()
        names = [_("(Sin perfil)")] + [profile.name for _identifier, profile in self.profiles]
        self._updating = True
        self.profile_drop.set_model(Gtk.StringList.new(names))
        index = 0
        for position, (identifier, _profile) in enumerate(self.profiles, 1):
            if identifier == previous:
                index = position
        self.profile_drop.set_selected(index)
        self._updating = False

    def _current_profile_id(self) -> int | None:
        index = self.profile_drop.get_selected()
        return self.profiles[index - 1][0] if 0 < index <= len(self.profiles) else None

    def _current_profile(self) -> Profile | None:
        index = self.profile_drop.get_selected()
        return self.profiles[index - 1][1] if 0 < index <= len(self.profiles) else None

    def _on_profile_changed(self, *_args) -> None:
        if not self._updating:
            self._refresh_items()

    def _new_profile(self, _button) -> None:
        ProfileWindow(self, self.store, None, None, self._profile_saved).present()

    def _edit_profile(self, _button) -> None:
        identifier, profile = self._current_profile_id(), self._current_profile()
        if identifier is None or profile is None:
            message(self, _("No hay ningún perfil seleccionado."), _("Crea uno con «Nuevo»."))
            return
        ProfileWindow(self, self.store, profile, identifier, self._profile_saved).present()

    def _profile_saved(self, identifier: int) -> None:
        self._reload_profiles(identifier)
        self._refresh_items()

    def _delete_profile(self, _button) -> None:
        identifier, profile = self._current_profile_id(), self._current_profile()
        if identifier is None or profile is None:
            return

        def delete() -> None:
            self.store.delete_profile(identifier)
            self._reload_profiles()
            self._refresh_items()

        confirm(self, _("¿Borrar el perfil «{name}»?").format(name=profile.name),
                _("Las ofertas guardadas no se borran."), _("Borrar"), delete)

    # --- búsquedas guardadas ----------------------------------------------------------------------
    def _reload_searches(self, select_id: int | None = None) -> None:
        everything = self.store.list_searches()
        self.last_search_id = next((s.id for s in everything if s.name == LAST_SEARCH), None)
        self.saved_searches = [s for s in everything if s.name != LAST_SEARCH]
        names = [_("(Búsqueda nueva)")] + [s.name for s in self.saved_searches]
        self._updating = True
        self.search_drop.set_model(Gtk.StringList.new(names))
        index = 0
        for position, saved in enumerate(self.saved_searches, 1):
            if saved.id == select_id:
                index = position
        self.search_drop.set_selected(index)
        self._updating = False

    def _selected_saved_search(self) -> SavedSearch | None:
        index = self.search_drop.get_selected()
        return self.saved_searches[index - 1] if 0 < index <= len(self.saved_searches) else None

    def _on_saved_search_chosen(self, *_args) -> None:
        saved = self._selected_saved_search()
        if self._updating or saved is None:
            return
        self._fill_query(saved.query, saved.sources)
        if saved.profile_id is not None:
            self._reload_profiles(saved.profile_id)
        self.current_search_id = saved.id
        self._load_results()

    def _save_search(self, _button) -> None:
        query = self._collect_query()
        if not query.keywords:
            message(self, _("Escribe primero el puesto o las palabras clave."))
            return
        current = self._selected_saved_search()
        default = current.name if current else query.keywords

        def save(name: str) -> None:
            existing = next((s for s in self.saved_searches if s.name == name), None)
            identifier = self.store.save_search(name, self._current_profile_id(), query, self._selected_sources(),
                                                existing.id if existing else None)
            self._reload_searches(identifier)
            self.current_search_id = identifier
            self.status.set_text(_("Búsqueda «{name}» guardada.").format(name=name))

        ask_text(self, _("Guardar búsqueda"), _("Nombre de la búsqueda"), default, save)

    def _delete_search(self, _button) -> None:
        saved = self._selected_saved_search()
        if saved is None:
            return

        def delete() -> None:
            self.store.delete_search(saved.id)
            self._reload_searches()

        confirm(self, _("¿Borrar la búsqueda «{name}»?").format(name=saved.name), "", _("Borrar"), delete)

    def _fill_query(self, query: SearchQuery, sources: list[str]) -> None:
        self.keywords.set_text(query.keywords)
        self.location.set_text(query.location)
        self.limit.set_value(query.limit)
        self.posted.set_selected(POSTED.index(query.posted) if query.posted in POSTED else 0)
        self.remote.set_active(query.remote)
        for source_id, check in self.source_checks.items():
            check.set_active(source_id in sources)
        self._update_estimate()

    def _collect_query(self) -> SearchQuery:
        return SearchQuery(self.keywords.get_text().strip(), self.location.get_text().strip(),
                           int(self.limit.get_value()), POSTED[self.posted.get_selected()], self.remote.get_active())

    def _selected_sources(self) -> list[str]:
        return [source_id for source_id, check in self.source_checks.items() if check.get_active()]

    def _update_estimate(self) -> None:
        runs = plan_search(self._collect_query(), self._selected_sources(), settings.budget_usd())
        if not runs:
            self.estimate.set_text(_("Elige al menos una fuente."))
            self.estimate.set_tooltip_text(None)
            return
        total = sum(run.estimate_usd for run in runs)
        if all(run.source.local for run in runs):
            text = _("Sin coste: se lee directamente de su web")
        else:
            text = _("Coste estimado en Apify: ≈ {cost} $ (tope {cap} $)").format(
                cost=f"{total:.3f}", cap=f"{settings.budget_usd():.2f}")
        previous, _unused = self._incremental_base(self._collect_query(), self._selected_sources())
        if previous is not None:   # el máximo no cambia, pero se pagará solo por lo que sea nuevo
            text += " · " + _("solo novedades desde el {date}").format(date=previous.ran_at[:10])
        self.estimate.set_text(text)
        self.estimate.set_tooltip_text(text)   # el texto entero, por si se ha acortado

    def _incremental_base(self, query: SearchQuery, sources: list[str]) -> tuple[SavedSearch | None, str]:
        """La búsqueda anterior y la ventana de fechas, si esta puede pedir solo novedades; si no, (None, "")."""
        if not self.incremental.get_active():
            return None, ""
        saved = self._selected_saved_search()
        target = saved.id if saved else self.last_search_id
        previous = next((s for s in self.store.list_searches() if s.id == target), None)
        if (previous is None or not previous.ran_at or not same_search(previous.query, query)
                or not set(sources) <= set(previous.sources)):
            return None, ""
        window = incremental_posted(query.posted, previous.ran_at, datetime.now(timezone.utc))
        return (previous, window) if window is not None else (None, "")

    # --- búsqueda ---------------------------------------------------------------------------------
    def _start_search(self, *_args) -> None:
        if self.searching:
            return
        query = self._collect_query()
        sources = self._selected_sources()
        if not query.keywords:
            message(self, _("Escribe el puesto o las palabras clave."))
            return
        if not sources:
            message(self, _("Elige al menos una fuente."))
            return
        token = ""
        if any(not SOURCES[source_id].local for source_id in sources):   # las fuentes locales no usan Apify
            try:
                token = token_store.get_token()
            except token_store.SecretsError as error:
                message(self, _("No hay un llavero disponible."), str(error))
                return
            if not token:
                message(self, _("Falta el token de Apify."), _("Añádelo en Preferencias (menú principal)."))
                return
        previous, window = self._incremental_base(query, sources)
        effective = replace(query, posted=window) if previous else query   # lo que se le pide a las fuentes
        base = prune_stale(self.store.jobs_for_search(previous.id), datetime.now(timezone.utc)) if previous else []
        runs = plan_search(effective, sources, settings.budget_usd())
        total = sum(run.estimate_usd for run in runs)

        def launch() -> None:
            self._run(token, effective, sources, runs, query, base)

        if total > CONFIRM_ABOVE_USD:
            confirm(self, _("Esta búsqueda costará aproximadamente {cost} $ en Apify.").format(cost=f"{total:.2f}"),
                    _("Es una estimación con los precios del plan gratuito; el tope de gasto es de {cap} $.")
                    .format(cap=f"{settings.budget_usd():.2f}"), _("Buscar"), launch)
        else:
            launch()

    def _run(self, token, effective, sources, runs, query, base) -> None:
        self.searching = True
        self.search_button.set_sensitive(False)
        self.spinner.start()

        def progress(name: str) -> None:
            GLib.idle_add(self.status.set_text, _("Buscando en {source}…").format(source=name))

        def work() -> None:
            results = run_search(token, effective, runs, progress=progress)
            GLib.idle_add(self._search_finished, results, query, sources, base)

        Thread(target=work, daemon=True).start()

    def _search_finished(self, results, query, sources, base) -> None:
        self.searching = False
        self.search_button.set_sensitive(True)
        self.spinner.stop()
        fresh = [job for result in results for job in result.jobs]
        found = merge_jobs([*base, *fresh])
        known = {job.key for job in base}
        new_count = sum(1 for job in found if job.key not in known)
        errors = [f"{result.source.name}: {result.error}" for result in results if result.error]
        if found or not errors:
            saved = self._selected_saved_search()
            search_id = saved.id if saved else self.store.save_search(
                LAST_SEARCH, self._current_profile_id(), query, sources, self.last_search_id)
            if not saved:
                self.last_search_id = search_id
            self.store.store_results(search_id, found)
            self.current_search_id = search_id
            self._load_results()
            self.status.set_text(ngettext("{count} oferta de {sources} fuente(s).",
                                          "{count} ofertas de {sources} fuente(s).", len(found)).format(
                                              count=len(found), sources=sum(1 for r in results if not r.error)))
            if base:
                self.status.set_text(self.status.get_text() + " " + ngettext(
                    "{new} nueva.", "{new} nuevas.", new_count).format(new=new_count))
        if errors:
            message(self, _("Alguna fuente ha fallado."), "\n".join(errors))
            if not found:
                self.status.set_text(_("La búsqueda no ha devuelto ofertas."))

    # --- resultados -------------------------------------------------------------------------------
    def _load_last_search(self) -> None:
        if self.last_search_id is None:
            return
        last = next((s for s in self.store.list_searches() if s.id == self.last_search_id), None)
        if last:
            self._fill_query(last.query, last.sources)
            if last.profile_id is not None:
                self._reload_profiles(last.profile_id)
        self.current_search_id = self.last_search_id
        self._load_results()

    def _load_results(self) -> None:
        self.jobs = self.store.jobs_for_search(self.current_search_id) if self.current_search_id else []
        self._refresh_items()

    def _refresh_items(self) -> None:
        profile = self._current_profile() or Profile(name="")
        self.evaluations = {job.key: evaluate(job, profile) for job in self.jobs}
        # de mejor a peor encaje ya en los datos, para que no dependa del estado del ColumnView
        ordered = sorted(self.jobs, key=lambda job: (self.evaluations[job.key].fit.rank,
                                                     self.evaluations[job.key].score or 0.0), reverse=True)
        items = [JobItem(job, self.evaluations[job.key]) for job in ordered]
        self.store_model.splice(0, self.store_model.get_n_items(), items)
        self._queue_ats(items, profile)
        self._sort_by_fit()
        self._reload_category_filter(profile)
        self._filters_changed()
        self._update_panorama(profile)

    # --- compatibilidad ATS en segundo plano ---------------------------------------------------------
    @staticmethod
    def _profile_key(profile: Profile) -> str:
        """Una huella del perfil: si cambia, las estimaciones guardadas ya no valen."""
        return hashlib.sha1(json.dumps(profile.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()

    def _ats_of(self, item: JobItem, profile: Profile) -> AtsEstimate:
        """La estimación de una oferta: la guardada o, si falta, se calcula ahora."""
        key = (item.job.key, self._ats_profile_key)
        if key not in self._ats_cache:
            self._ats_cache[key] = estimate_ats(item.job, profile)
        if item.ats is None:
            item.set_ats(self._ats_cache[key])
        return self._ats_cache[key]

    def _queue_ats(self, items: list[JobItem], profile: Profile) -> None:
        """Pone las estimaciones ya conocidas y calcula el resto por tandas, para que la ventana no se bloquee."""
        self._ats_generation += 1   # una tanda anterior, si la hay, se abandona
        self._ats_profile_key = self._profile_key(profile)
        pending = []
        for item in items:
            cached = self._ats_cache.get((item.job.key, self._ats_profile_key))
            if cached is not None:
                item.set_ats(cached)
            else:
                pending.append(item)
        if pending:
            GLib.idle_add(self._ats_step, self._ats_generation, pending, profile)

    def _ats_step(self, generation: int, pending: list[JobItem], profile: Profile) -> bool:
        if generation != self._ats_generation:
            return False
        for item in pending[:ATS_CHUNK]:
            self._ats_of(item, profile)
        del pending[:ATS_CHUNK]
        self._ats_changed(final=not pending)
        return bool(pending)

    def _ats_changed(self, final: bool) -> None:
        """Tras una tanda: si hay un filtro o un orden por ATS, se reaplica; al acabar, se refresca el contador."""
        if self.filter_ats.get_selected() > 0:
            self.filter.changed(Gtk.FilterChange.DIFFERENT)
        sorter = self.view.get_sorter()
        primary = sorter.get_primary_sort_column() if sorter is not None else None
        if primary is not None and primary.get_title() == _("ATS"):
            primary.get_sorter().changed(Gtk.SorterChange.DIFFERENT)
        if final:
            self._update_counter()

    def _reload_category_filter(self, profile: Profile) -> None:
        names = [category.name for category in profile.categories]
        previous = self.filter_category.get_selected()
        labels = [_("Tipo: todos"), *names, _("Otros")]
        self.filter_category.set_model(Gtk.StringList.new(labels))
        self.filter_category.set_selected(previous if previous < len(labels) else 0)
        self._category_names = names

    def _filters_changed(self) -> None:
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_counter()

    def _item_matches(self, item: JobItem, *_extra) -> bool:
        job, evaluation = item.job, item.evaluation
        text = normalize(self.filter_text.get_text())
        if text and text not in normalize(f"{job.company} {job.title} {job.text}"):
            return False
        wanted_fit = FIT_FILTERS[self.filter_fit.get_selected()]
        if wanted_fit is not None and evaluation.fit is not wanted_fit:
            return False
        wanted_ats = ATS_FILTERS[self.filter_ats.get_selected()]
        if wanted_ats is not None and not (item.ats_percent >= 0 and wanted_ats[0] <= item.ats_percent < wanted_ats[1]):
            return False   # sin calcular todavía no entra en un filtro por rango
        wanted_mode = MODE_FILTERS[self.filter_mode.get_selected()]
        if wanted_mode is not None and job.work_mode is not wanted_mode:
            return False
        category = self.filter_category.get_selected()
        names = getattr(self, "_category_names", [])
        if category > 0:
            if category <= len(names):
                if evaluation.category != names[category - 1]:
                    return False
            elif evaluation.category:   # «Otros»: ninguno de los tipos del perfil
                return False
        state = STATE_FILTERS[self.filter_state.get_selected()]
        if state == "process":
            return stage_of(job).is_open
        if state == "notes":
            return job.has_tracking
        if state == "active":
            return job.state is not JobState.DISCARDED
        return state == "all" or job.state.value == state

    def _update_counter(self) -> None:
        self.counter.set_text(_("{shown} de {total} ofertas").format(
            shown=self.filter_model.get_n_items(), total=self.store_model.get_n_items()))

    def _update_panorama(self, profile: Profile) -> None:
        self.market.invalidate()
        self.map_page.invalidate()
        if self.map_page.get_mapped():
            GLib.idle_add(self.map_page.refresh)
        if self.market.get_mapped():   # abierta la pestaña mientras llegan datos: se recalcula
            GLib.idle_add(self.market.refresh)
        child = self.panorama_box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.panorama_box.remove(child)
            child = following
        active = [job for job in self.jobs if job.state is not JobState.DISCARDED]
        if not active:
            self.panorama_box.append(Gtk.Label(label=_("Todavía no hay ofertas: lanza una búsqueda."), xalign=0))
            return
        panorama = build_panorama(active, self.evaluations, profile if profile.name else None)
        title = Gtk.Label(xalign=0, wrap=True, use_markup=True)
        title.set_markup("<b>{}</b>".format(GLib.markup_escape_text(
            ngettext("Qué piden: {detailed} oferta con detalle de {total}",
                     "Qué piden: {detailed} ofertas con detalle de {total}", panorama.detailed).format(
                         detailed=panorama.detailed, total=panorama.total))))
        self.panorama_box.append(title)
        grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        top = [item for item in panorama.requirements if item.count > 0][:20]
        maximum = max((item.count for item in top), default=1)
        for row, item in enumerate(top):
            grid.attach(Gtk.Label(label=item.name, xalign=0), 0, row, 1, 1)
            bar = Gtk.ProgressBar(fraction=item.count / maximum, hexpand=True, valign=Gtk.Align.CENTER)
            bar.set_size_request(280, -1)
            grid.attach(bar, 1, row, 1, 1)
            grid.attach(Gtk.Label(label=str(item.count), xalign=1), 2, row, 1, 1)
        self.panorama_box.append(grid)
        self._build_gaps(active, profile)
        if panorama.insights:
            self._append_info_card(panorama)

    def _append_info_card(self, panorama) -> None:
        """El recuadro azul de abajo del todo con lo que se ve en la muestra: la primera conclusión resaltada, los
        recuentos con barras (lo más pedido, el encaje, el salario y el remoto) y el resto como viñetas."""
        rows = self._skill_card("info", pick_icon("dialog-information", "help-about"),
                                _("Lo que se ve en esta muestra"), "")
        while (child := rows.get_first_child()) is not None:
            rows.remove(child)
        total, detailed = max(panorama.total, 1), max(panorama.detailed, 1)
        top = [item for item in panorama.requirements if item.count > 0][:3]
        for number, (key, text) in enumerate(panorama.keyed):
            if key == "top":
                rows.append(self._info_line(text, first=number == 0))
                if top:
                    rows.append(self._bar_grid([
                        (item.name, item.count / detailed,
                         f"{item.count} / {panorama.detailed} ({round(100 * item.count / detailed)} %)", "")
                        for item in top]))
            elif key == "fit":
                high, medium, low = panorama.fit_counts
                rows.append(self._info_line(_("Encaje"), bold=True))
                rows.append(self._bar_grid([
                    (Fit.HIGH.label, high / total, f"{high} ({round(100 * high / total)} %)", "bar-fit-high"),
                    (Fit.MEDIUM.label, medium / total, f"{medium} ({round(100 * medium / total)} %)", "bar-fit-medium"),
                    (Fit.LOW.label, low / total, f"{low} ({round(100 * low / total)} %)", "bar-fit-low")]))
            elif key == "salary":
                rows.append(self._bar_grid([(_("Con salario"), panorama.salary_count / total, text, "")]))
            elif key == "remote":
                rows.append(self._bar_grid([(_("En remoto"), panorama.remote_count / total, text, "")]))
            else:
                rows.append(self._info_line(text, first=number == 0))

    @staticmethod
    def _info_line(text: str, first: bool = False, bold: bool = False) -> Gtk.Label:
        line = Gtk.Label(xalign=0, wrap=True, use_markup=True)
        escaped = GLib.markup_escape_text(text)
        line.set_markup(f"<big><b>{escaped}</b></big>" if first else f"<b>{escaped}</b>" if bold else f"• {escaped}")
        return line

    @staticmethod
    def _bar_grid(rows: list[tuple[str, float, str, str]]) -> Gtk.Grid:
        """Filas «nombre · barra · texto» como las de los cuadros rojo y verde; la clase da el color de la barra."""
        grid = Gtk.Grid(column_spacing=12, row_spacing=4, margin_start=6)
        for number, (name, fraction, text, css) in enumerate(rows):
            title = Gtk.Label(xalign=0)
            title.set_markup(f"<b>{GLib.markup_escape_text(name)}</b>")
            grid.attach(title, 0, number, 1, 1)
            bar = Gtk.ProgressBar(fraction=max(0.0, min(1.0, fraction)), valign=Gtk.Align.CENTER)
            bar.set_size_request(150, -1)
            if css:
                bar.add_css_class(css)
            grid.attach(bar, 1, number, 1, 1)
            grid.attach(Gtk.Label(label=text, xalign=0, wrap=True, hexpand=True), 2, number, 1, 1)
        return grid

    def _build_gaps(self, active: list[Job], profile: Profile) -> None:
        """Los cuadros «Qué te falta más veces» y «Tus puntos fuertes»: se calculan en segundo plano porque recorren
        todas las ofertas."""
        if not profile.name:
            return
        gaps_box = self._skill_card("gap", pick_icon("dialog-warning", "emblem-important"), _("Qué te falta más veces"),
                                    _("Lo que piden tus ofertas y no cubres: lo que no está en tu perfil y los "
                                      "elementos de tus radares con nivel bajo. Formarte en esto es lo que más "
                                      "subiría tu encaje."))
        strengths_box = self._skill_card("strength", pick_icon("emblem-ok", "starred", "emblem-default"),
                                         _("Tus puntos fuertes"),
                                         _("Lo que ya tienes y más piden tus ofertas: destácalo en tu CV y en las "
                                           "entrevistas."))
        self._gaps_token = getattr(self, "_gaps_token", 0) + 1
        token, evaluations = self._gaps_token, dict(self.evaluations)

        def work() -> None:
            gaps = find_gaps(active, evaluations, profile)
            strengths = find_strengths(active, evaluations, profile)
            GLib.idle_add(self._show_skills, token, gaps_box, strengths_box, gaps, strengths)

        Thread(target=work, daemon=True).start()

    def _skill_card(self, kind: str, icon: str, title: str, hint: str) -> Gtk.Box:
        """Un cuadro de color con título y explicación; devuelve la caja donde irán las filas."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6)
        card.add_css_class("skill-card")
        card.add_css_class(f"skill-card-{kind}")
        head = Gtk.Box(spacing=8)
        if icon:
            head.append(Gtk.Image(icon_name=icon, pixel_size=22))
        label = Gtk.Label(xalign=0, use_markup=True)
        label.set_markup(f"<big><b>{GLib.markup_escape_text(title)}</b></big>")
        head.append(label)
        card.append(head)
        if hint:
            explanation = Gtk.Label(label=hint, xalign=0, wrap=True)
            explanation.add_css_class("dim-label")
            card.append(explanation)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=4)
        rows.append(Gtk.Label(label=_("Calculando…"), xalign=0))
        card.append(rows)
        self.panorama_box.append(card)
        return rows

    def _show_skills(self, token: int, gaps_box: Gtk.Box, strengths_box: Gtk.Box, gaps: list[Gap],
                     strengths: list[Strength]) -> bool:
        if token != self._gaps_token:
            return False   # el panorama se ha vuelto a dibujar mientras tanto
        self._fill_skill_rows(gaps_box, [(gap.name, gap.relevant or gap.offers, gap_text(gap)) for gap in gaps],
                              _("No hay huecos que destacar con las ofertas que tienen descripción completa."),
                              study=True)
        self._fill_skill_rows(strengths_box, [(item.name, item.relevant or item.offers, strength_text(item))
                                              for item in strengths],
                              _("Ninguna oferta con descripción completa cita lo que tienes en el perfil."))
        return False

    @staticmethod
    def _fill_skill_rows(box: Gtk.Box, rows: list[tuple[str, int, str]], empty: str, study: bool = False) -> None:
        while (child := box.get_first_child()) is not None:
            box.remove(child)
        if not rows:
            box.append(Gtk.Label(label=empty, xalign=0, wrap=True))
            return
        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        maximum = max(weight for _name, weight, _text in rows) or 1
        for number, (name, weight, text) in enumerate(rows):
            title = Gtk.Label(xalign=0)
            title.set_markup(f"<b>{GLib.markup_escape_text(name)}</b>")
            grid.attach(title, 0, number, 1, 1)
            bar = Gtk.ProgressBar(fraction=weight / maximum, valign=Gtk.Align.CENTER)
            bar.set_size_request(120, -1)
            grid.attach(bar, 1, number, 1, 1)
            grid.attach(Gtk.Label(label=text, xalign=0, wrap=True, hexpand=True), 2, number, 1, 1)
            if study:   # lo que te falta: certificaciones oficiales y cursos para reforzarlo
                grid.attach(study_button(name), 3, number, 1, 1)
        box.append(grid)

    # --- detalle y estados -------------------------------------------------------------------------
    def _selected_item(self) -> JobItem | None:
        return self.selection.get_selected_item()

    def _on_selection_changed(self, *_args) -> None:
        self._set_detail(self._selected_item())

    def _set_detail(self, item: JobItem | None) -> None:
        for widget in (self.open_button, self.cv_button, *self.state_buttons.values()):
            widget.set_sensitive(item is not None)
        if item is None:
            self.detail_view.show_message(_("Elige una oferta para ver qué criterios cumple."))
            self.radar.set_data([], Fit.UNKNOWN)
            self.notes_panel.load(None)
            self.tracking_panel.load(None)
            self._mark_tabs(None)
            return
        job = item.job
        profile = self._current_profile() or Profile(name="")
        ats = self._ats_of(item, profile)
        self.radar.set_data(build_radars(job, profile), item.evaluation.fit, ats)
        if self.notes_panel.job is not job:   # al marcar un estado se repinta el panel sin tocar lo que se escribe
            self.notes_panel.load(job)
            self.tracking_panel.load(job)
        self._mark_tabs(job)
        self.detail_view.show_job(job, item.evaluation, profile, salary_text(job), ats)
        for state, button in self.state_buttons.items():
            button.get_child().get_last_child().set_label(
                {JobState.FAVORITE: _("Favorita"), JobState.APPLIED: _("Postulada"),
                 JobState.DISCARDED: _("Descartar")}[state] if job.state is not state else _("Quitar marca"))

    def _toggle_state(self, state: JobState) -> None:
        item = self._selected_item()
        if item is None:
            return
        item.job.state = JobState.NEW if item.job.state is state else state
        self.store.set_state(item.job.key, item.job.state)
        found, position = self.store_model.find(item)
        if found:   # vuelve a pintar su fila (la columna «Estado»)
            self.store_model.items_changed(position, 1, 1)
        self._filters_changed()
        self._set_detail(item)
        self._update_panorama(self._current_profile() or Profile(name=""))

    @staticmethod
    def _row_signature(job: Job) -> tuple[str, str]:
        """Lo que se ve de su seguimiento en la fila de la tabla: el icono de notas y la fase."""
        return notes_mark(job, today().isoformat()), job.stage

    def _notes_changed(self, job: Job, notes: str) -> None:
        job.notes = notes
        self.store.set_notes(job.key, notes)
        self._after_tracking_change(job)

    def _tracking_changed(self, job: Job) -> None:
        """El panel de seguimiento ya ha guardado: aquí solo se repinta lo que depende de ello."""
        self._after_tracking_change(job)

    def _after_tracking_change(self, job: Job) -> None:
        self._mark_tabs(job)
        signature = self._row_signature(job)
        if self._row_signatures.get(job.key) != signature:   # no se repinta la fila a cada tecla
            self._row_signatures[job.key] = signature
            self._repaint_row(job)
        if STATE_FILTERS[self.filter_state.get_selected()] in ("notes", "process"):
            self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self._announce_reminders()

    def _repaint_row(self, job: Job) -> None:
        for position in range(self.store_model.get_n_items()):
            if self.store_model.get_item(position).job is job:
                self.store_model.items_changed(position, 1, 1)
                return

    def _announce_reminders(self) -> None:
        """Avisa en la barra de estado de los recordatorios que vencen hoy o antes (de cualquier búsqueda)."""
        due = self.store.due_reminders(today().isoformat())
        if not due or self.searching:
            return
        titles = ", ".join(f"«{title or key}»" for key, title, _day in due[:3])
        self.status.set_text(ngettext("Tienes {count} recordatorio para hoy o vencido: {titles}.",
                                      "Tienes {count} recordatorios para hoy o vencidos: {titles}.",
                                      len(due)).format(count=len(due), titles=titles))

    def _adapt_cv(self, _button) -> None:
        item = self._selected_item()
        profile = self._current_profile()
        if item is None:
            return
        if profile is None:
            message(self, _("Crea un perfil con tus datos para poder adaptar tu currículum."))
            return
        if not vte_available():
            message(self, _("Falta el terminal embebido: instala el paquete gir1.2-vte-3.91."))
            return
        try:
            work = prepare_workspace(DATA_DIR / "cv", item.job, item.evaluation, profile)
            argv = build_argv(settings.assistant_command(),
                              build_prompt(settings.assistant_prompt(), work.offer, work.cv, work.upload, work.output))
        except (OSError, ValueError) as error:
            message(self, _("No se pudo preparar el asistente."), str(error))
            return
        window = AssistantWindow(self, work, argv, item.job)
        self._assistant_windows = [w for w in getattr(self, "_assistant_windows", []) if not w.is_destroyed()] + [window]
        window.present()

    def _open_job(self, _button) -> None:
        item = self._selected_item()
        if item is None or not item.job.url.startswith(("http://", "https://")):
            message(self, _("Esta oferta no tiene un enlace utilizable."))
            return
        Gtk.UriLauncher.new(item.job.url).launch(self, None, None)

    # --- exportar ---------------------------------------------------------------------------------
    def _visible_jobs(self) -> list[Job]:
        return [self.sort_model.get_item(i).job for i in range(self.sort_model.get_n_items())]

    def _export(self, kind: str) -> None:
        jobs = self._visible_jobs()
        if not jobs:
            message(self, _("No hay ofertas que exportar."), _("Lanza una búsqueda o cambia los filtros."))
            return
        dialog = Gtk.FileDialog(title=_("Exportar ofertas"))
        dialog.set_initial_name("grepleo.html" if kind == "html" else "grepleo.csv")

        def saved(source, result) -> None:
            try:
                file = source.save_finish(result)
            except GLib.Error:
                return   # el usuario canceló
            path = Path(file.get_path())
            try:
                if kind == "csv":
                    export_csv(path, jobs, self.evaluations, source_names())
                else:
                    profile = self._current_profile()
                    panorama = build_panorama(jobs, self.evaluations, profile)
                    export_html(path, profile, jobs, self.evaluations, panorama, source_names(),
                                _("Radar de ofertas: {query}").format(query=self.keywords.get_text().strip() or "—"),
                                language=(settings.language() or "es"))
            except OSError as error:
                message(self, _("No se pudo guardar el archivo."), str(error))
                return
            self.status.set_text(_("Exportado: {path}").format(path=path))

        dialog.save(self, None, saved)

    # --- menú ------------------------------------------------------------------------------------
    def _open_preferences(self) -> None:
        from .preferences import PreferencesWindow
        PreferencesWindow(self.get_application(), self.searching).present()
        self._update_estimate()

    def _open_about(self) -> None:
        about = Gtk.AboutDialog(
            transient_for=self, modal=True, program_name="Grepleo", version=__version__,
            comments=_("Busca empleo en InfoJobs, Indeed, LinkedIn, Tecnoempleo y Michael Page, y comprueba qué criterios cumples en cada oferta."),
            website=REPO_URL, website_label=REPO_URL.removeprefix("https://"),
            authors=[f"{AUTHOR} <{AUTHOR_EMAIL}>"], copyright=f"© 2026 {AUTHOR}",
            license_type=Gtk.License.GPL_3_0, translator_credits=_("translator-credits"))
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        if theme.has_icon("grepleo"):
            about.set_logo_icon_name("grepleo")
        else:
            logo = Path(__file__).resolve().parents[3] / "grepleo.svg"   # solo al ejecutar desde el repositorio
            if logo.exists():
                about.set_logo(Gdk.Texture.new_from_filename(str(logo)))
        about.add_credit_section(_("Servicios de terceros"), [
            "Apify https://apify.com/",
            _("Actors de la comunidad de Apify para InfoJobs, Indeed, LinkedIn y Tecnoempleo"),
            "Michael Page https://www.michaelpage.es/",
            _("Michael Page se lee directamente de su web pública, sin Apify")])
        about.present()


def run_gui() -> None:
    class App(Gtk.Application):
        def do_activate(self):
            windows = self.get_windows()
            if windows:   # segunda activación: se reutiliza la ventana
                windows[0].present()
                return
            gtk_settings = Gtk.Settings.get_default()
            APPEARANCE.system = gtk_settings.get_property("gtk-theme-name")
            chosen = settings.dark_mode()
            APPEARANCE.dark = is_dark_theme(APPEARANCE.system) if chosen is None else chosen
            if chosen is not None:   # antes de presentar la ventana: en caliente Cinnamon no repinta
                gtk_settings.set_property("gtk-theme-name", theme_variant(APPEARANCE.system, chosen))
            install_css()
            MainWindow(self, Store()).present()

    App(application_id="io.github.seguidodoblado.Grepleo").run(None)

