"""Ventana principal: búsqueda, resultados con su encaje, detalle de criterios, panorama y exportación."""
from pathlib import Path
from threading import Thread

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk

from .. import __version__, settings
from .. import secrets as token_store
from ..i18n import _, ngettext
from ..matching import evaluate
from ..models import Evaluation, Fit, Job, JobState
from ..panorama import build_panorama
from ..profiles import Profile
from ..report import export_csv, export_html
from ..sources import POSTED, SOURCES, SearchQuery, plan_search, run_search
from ..storage import SavedSearch, Store
from ..textutil import normalize
from .common import APPEARANCE, ask_text, confirm, icon_button, install_css, labeled, message
from .profile_dialog import ProfileWindow
from .theming import is_dark_theme, theme_variant

AUTHOR = "Jose Antonio Seguido Doblado"
AUTHOR_EMAIL = "jose.antonio.seguido@gmail.com"
REPO_URL = "https://github.com/seguidodoblado/grepleo"
LAST_SEARCH = "·última·"          # nombre reservado de la búsqueda que se guarda sola
CONFIRM_ABOVE_USD = 0.25          # por encima de este coste estimado se pide confirmación
STATE_FILTERS = ("active", "all", "favorite", "applied", "discarded")
FIT_FILTERS = (None, Fit.HIGH, Fit.MEDIUM, Fit.LOW, Fit.UNKNOWN)


def posted_labels() -> list[str]:
    return [_("Cualquier fecha"), _("Últimas 24 horas"), _("Última semana"), _("Último mes")]


def state_filter_labels() -> list[str]:
    return [_("Activas (sin descartar)"), _("Todas"), _("Favoritas"), _("Postuladas"), _("Descartadas")]


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
    """Una fila de la tabla: la oferta y su evaluación."""

    def __init__(self, job: Job, evaluation: Evaluation) -> None:
        super().__init__()
        self.job = job
        self.evaluation = evaluation


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
        area.append(query_row)

        action_row = Gtk.Box(spacing=12)
        self.source_checks: dict[str, Gtk.CheckButton] = {}
        for source_id, source in SOURCES.items():
            check = Gtk.CheckButton(label=source.name, active=True)
            check.connect("toggled", lambda *_args: self._update_estimate())
            self.source_checks[source_id] = check
            action_row.append(check)
        self.estimate = Gtk.Label(xalign=0, hexpand=True)
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

        columns = (
            (_("Empresa · Puesto"), lambda item: f"{item.job.company or '—'}\n{item.job.title}", 240, "company"),
            (_("Tipo"), lambda item: item.evaluation.category or "—", 90, "category"),
            (_("Ubicación"), lambda item: f"{item.job.location or '—'}\n{item.job.work_mode.label}", 150, "location"),
            (_("Salario"), lambda item: salary_text(item.job), 120, "salary"),
            (_("Experiencia"), lambda item: item.job.experience_text or "—", 110, "experience"),
            (_("Criterios"), lambda item: criteria_text(item.evaluation), 420, None),
            (_("Encaje"), lambda item: f"{item.evaluation.fit.label}\n{item.evaluation.summary}", 90, "fit"),
            (_("Estado"), lambda item: item.job.state.label, 90, "state"),
            (_("Fuente"), lambda item: source_names().get(item.job.source, item.job.source), 90, "source"),
        )
        self.fit_column = None
        for title, getter, width, sort_key in columns:
            column = self._text_column(title, getter, width, sort_key, is_fit=sort_key == "fit")
            self.view.append_column(column)
            if sort_key == "fit":
                self.fit_column = column
        if self.fit_column is not None:
            self.view.sort_by_column(self.fit_column, Gtk.SortType.DESCENDING)

        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=280)
        scroll.set_child(self.view)
        self.detail = self._build_detail()
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        paned.set_start_child(scroll)
        paned.set_end_child(self.detail)
        paned.set_position(380)
        page.append(paned)
        return page

    def _text_column(self, title, getter, width, sort_key, is_fit=False) -> Gtk.ColumnViewColumn:
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, row):
            label = Gtk.Label(xalign=0, wrap=True, margin_top=4, margin_bottom=4, margin_start=6, margin_end=6,
                              max_width_chars=70, valign=Gtk.Align.START)
            row.set_child(label)

        def bind(_factory, row):
            label = row.get_child()
            item = row.get_item()
            label.set_text(getter(item))
            for fit in Fit:
                label.remove_css_class(f"fit-{fit.value}")
            if is_fit:
                label.add_css_class(f"fit-{item.evaluation.fit.value}")
                label.set_halign(Gtk.Align.START)

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        column = Gtk.ColumnViewColumn.new(title, factory)
        column.set_resizable(True)
        column.set_fixed_width(width)
        if sort_key:
            column.set_sorter(Gtk.CustomSorter.new(self._sorter_for(sort_key)))
        return column

    @staticmethod
    def _sorter_for(key):
        def value(item):
            if key == "fit":
                return (item.evaluation.fit.rank, item.evaluation.score or 0.0)
            if key == "salary":
                top = item.job.salary_max if item.job.salary_max is not None else item.job.salary_min
                return (top is not None, top or 0.0)
            mapping = {"company": item.job.company, "category": item.evaluation.category,
                       "location": item.job.location, "experience": item.job.experience_text,
                       "state": item.job.state.value, "source": item.job.source}
            return normalize(mapping.get(key, ""))

        def compare(first, second, *_extra):
            a, b = value(first), value(second)
            return (a > b) - (a < b)

        return compare

    def _build_detail(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8)
        self.detail_label = Gtk.Label(xalign=0, yalign=0, wrap=True, selectable=True, use_markup=True)
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=140)
        scroll.set_child(self.detail_label)
        box.append(scroll)
        buttons = Gtk.Box(spacing=8)
        self.open_button = icon_button(("web-browser", "applications-internet"), _("Abrir oferta"))
        self.open_button.connect("clicked", self._open_job)
        buttons.append(self.open_button)
        self.state_buttons: dict[JobState, Gtk.Button] = {}
        for state, text in ((JobState.FAVORITE, _("Favorita")), (JobState.APPLIED, _("Postulada")),
                            (JobState.DISCARDED, _("Descartar"))):
            button = Gtk.Button(label=text)
            button.connect("clicked", lambda _button, s=state: self._toggle_state(s))
            self.state_buttons[state] = button
            buttons.append(button)
        box.append(buttons)
        self._set_detail(None)
        return box

    def _build_panorama_page(self) -> Gtk.ScrolledWindow:
        self.panorama_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                                    margin_bottom=12, margin_start=12, margin_end=12)
        scroll = Gtk.ScrolledWindow(vexpand=True)
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
            return
        total = sum(run.estimate_usd for run in runs)
        self.estimate.set_text(_("Coste estimado en Apify: ≈ {cost} $ (tope {cap} $)").format(
            cost=f"{total:.3f}", cap=f"{settings.budget_usd():.2f}"))

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
        try:
            token = token_store.get_token()
        except token_store.SecretsError as error:
            message(self, _("No hay un llavero disponible."), str(error))
            return
        if not token:
            message(self, _("Falta el token de Apify."), _("Añádelo en Preferencias (menú principal)."))
            return
        runs = plan_search(query, sources, settings.budget_usd())
        total = sum(run.estimate_usd for run in runs)

        def launch() -> None:
            self._run(token, query, sources, runs)

        if total > CONFIRM_ABOVE_USD:
            confirm(self, _("Esta búsqueda costará aproximadamente {cost} $ en Apify.").format(cost=f"{total:.2f}"),
                    _("Es una estimación con los precios del plan gratuito; el tope de gasto es de {cap} $.")
                    .format(cap=f"{settings.budget_usd():.2f}"), _("Buscar"), launch)
        else:
            launch()

    def _run(self, token, query, sources, runs) -> None:
        self.searching = True
        self.search_button.set_sensitive(False)
        self.spinner.start()

        def progress(name: str) -> None:
            GLib.idle_add(self.status.set_text, _("Buscando en {source}…").format(source=name))

        def work() -> None:
            results = run_search(token, query, runs, progress=progress)
            GLib.idle_add(self._search_finished, results, query, sources)

        Thread(target=work, daemon=True).start()

    def _search_finished(self, results, query, sources) -> None:
        self.searching = False
        self.search_button.set_sensitive(True)
        self.spinner.stop()
        found = merge_jobs([job for result in results for job in result.jobs])
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
        self.store_model.splice(0, self.store_model.get_n_items(),
                                [JobItem(job, self.evaluations[job.key]) for job in self.jobs])
        self._reload_category_filter(profile)
        self._filters_changed()
        self._update_panorama(profile)

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
        category = self.filter_category.get_selected()
        names = getattr(self, "_category_names", [])
        if category > 0:
            if category <= len(names):
                if evaluation.category != names[category - 1]:
                    return False
            elif evaluation.category:   # «Otros»: ninguno de los tipos del perfil
                return False
        state = STATE_FILTERS[self.filter_state.get_selected()]
        if state == "active":
            return job.state is not JobState.DISCARDED
        return state == "all" or job.state.value == state

    def _update_counter(self) -> None:
        self.counter.set_text(_("{shown} de {total} ofertas").format(
            shown=self.filter_model.get_n_items(), total=self.store_model.get_n_items()))

    def _update_panorama(self, profile: Profile) -> None:
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
        heading = Gtk.Label(xalign=0, use_markup=True)
        heading.set_markup("<b>{}</b>".format(GLib.markup_escape_text(_("Lo que se ve en esta muestra"))))
        self.panorama_box.append(heading)
        for text in panorama.insights:
            self.panorama_box.append(Gtk.Label(label="• " + text, xalign=0, wrap=True, selectable=True))

    # --- detalle y estados -------------------------------------------------------------------------
    def _selected_item(self) -> JobItem | None:
        return self.selection.get_selected_item()

    def _on_selection_changed(self, *_args) -> None:
        self._set_detail(self._selected_item())

    def _set_detail(self, item: JobItem | None) -> None:
        for widget in (self.open_button, *self.state_buttons.values()):
            widget.set_sensitive(item is not None)
        if item is None:
            self.detail_label.set_markup("<i>{}</i>".format(GLib.markup_escape_text(
                _("Elige una oferta para ver qué criterios cumple."))))
            return
        job, evaluation = item.job, item.evaluation
        esc = GLib.markup_escape_text
        lines = [f"<b>{esc(job.title)}</b>",
                 esc(" · ".join(part for part in (job.company, job.location, job.work_mode.label,
                                                  salary_text(job), job.experience_text) if part and part != "—"))]
        notes = [_("Encaje: {fit}").format(fit=evaluation.fit.label)]
        if not job.full_description:
            notes.append(_("Ficha resumida"))
        if job.closed:
            notes.append(_("Posiblemente cerrada"))
        if job.posted:
            notes.append(_("Publicada el {date}").format(date=job.posted))
        lines.append(esc(" · ".join(notes)))
        lines.append("")
        lines.extend(f"{item_.status.symbol}  <b>{esc(item_.name)}</b> — {esc(item_.detail)}"
                     for item_ in evaluation.criteria)
        if job.description:
            excerpt = job.description if len(job.description) <= 900 else job.description[:900] + "…"
            lines.extend(["", esc(excerpt)])
        self.detail_label.set_markup("\n".join(lines))
        for state, button in self.state_buttons.items():
            button.set_label({JobState.FAVORITE: _("Favorita"), JobState.APPLIED: _("Postulada"),
                              JobState.DISCARDED: _("Descartar")}[state] if job.state is not state
                             else _("Quitar marca"))

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
            comments=_("Busca empleo en InfoJobs, Indeed y LinkedIn y comprueba qué criterios cumples en cada oferta."),
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
            _("Actors de la comunidad de Apify para InfoJobs, Indeed y LinkedIn")])
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

