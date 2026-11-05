"""La ventana «Habilidades»: tus habilidades por grupos, cada una con un deslizador de 0 a 10 y la escala de niveles a la vista."""
import copy
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..i18n import _
from ..models import Fit
from ..panorama import DEFAULT_CATALOG
from ..profiles import MAX_AXES, MIN_AXES, Profile, parse_term
from ..radar import suggest_radars
from ..similar import aliases
from ..skills import SOFT_VOCABULARY
from ..skills_edit import (
    RADAR,
    SOFT,
    SkillGroup,
    SkillItem,
    SkillsState,
    apply_state,
    level_meaning,
    level_scale,
    level_title,
    other_name,
)
from .common import block_parent, pick_icon, wide_scrollbars
from .radar_view import RadarView


def split_spec(spec: str) -> tuple[str, str]:
    """«AWS|amazon web services» → («AWS», «amazon web services»): el nombre y los sinónimos, para dos casillas."""
    name, *synonyms = [part.strip() for part in spec.split("|") if part.strip()] or [""]
    return name, ", ".join(synonyms)


def join_spec(name: str, synonyms: str) -> str:
    """Lo contrario: el nombre y los sinónimos separados por comas, en el formato «nombre|sinónimo|sinónimo»."""
    parts = [name.strip(), *(part.strip() for part in synonyms.replace("|", ",").split(","))]
    return "|".join(part for part in parts if part)


class SkillRow(Gtk.Box):
    """Una habilidad: su nombre, sus sinónimos, un deslizador de 0 a 10 con su valor y lo que significa ese nivel."""

    def __init__(self, item: SkillItem, on_change: Callable[["SkillRow"], None],
                 on_remove: Callable[["SkillRow"], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=4, margin_bottom=4)
        self.add_css_class("card")
        self.item = item
        self._on_change = on_change
        self._loading = True
        name, synonyms = split_spec(item.spec)
        top = Gtk.Box(spacing=8, margin_top=6, margin_start=8, margin_end=8)
        self.name = Gtk.Entry(text=name, placeholder_text=_("Habilidad (AWS, Python, Scrum…)"), width_chars=22)
        self.synonyms = Gtk.Entry(text=synonyms, hexpand=True, placeholder_text=_("Sinónimos, separados por comas"))
        remove = Gtk.Button(icon_name=pick_icon("user-trash", "edit-delete"), tooltip_text=_("Quitar esta habilidad"))
        remove.connect("clicked", lambda _button: on_remove(self))
        for widget in (self.name, self.synonyms, remove):
            top.append(widget)
        self.append(top)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 10, 1)
        self.scale.set_value(item.level)
        self.scale.set_draw_value(True)
        self.scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.scale.set_hexpand(True)
        self.scale.set_margin_start(8)
        self.scale.set_margin_end(8)
        for mark in range(11):
            self.scale.add_mark(mark, Gtk.PositionType.BOTTOM, None)
        self.append(self.scale)
        self.meaning = Gtk.Label(xalign=0, margin_start=8, margin_end=8, margin_bottom=6, wrap=True)
        self.meaning.add_css_class("dim-label")
        self.append(self.meaning)
        self.name.connect("changed", self._changed)
        self.synonyms.connect("changed", self._changed)
        self.scale.connect("value-changed", self._changed)
        focus = Gtk.EventControllerFocus()
        focus.connect("enter", lambda _controller: self._on_change(self))
        self.add_controller(focus)
        self._loading = False
        self._refresh_meaning()

    def _refresh_meaning(self) -> None:
        level = round(self.scale.get_value())
        self.meaning.set_text(f"{level} · {level_title(level)}")
        self.meaning.set_tooltip_text(level_meaning(level))

    def _changed(self, *_args) -> None:
        if self._loading:
            return
        self.item.spec = join_spec(self.name.get_text(), self.synonyms.get_text())
        self.item.level = round(self.scale.get_value())
        self._refresh_meaning()
        self._on_change(self)

    def set_level(self, level: int) -> None:
        self.scale.set_value(max(0, min(10, level)))


class SkillsWindow(Gtk.Window):
    """Los grupos a la izquierda, las habilidades del grupo elegido en el centro y la escala de niveles a la derecha.

    Trabaja sobre una copia: `on_apply(state)` solo se llama al pulsar «Aplicar»."""

    def __init__(self, parent: Gtk.Window, state: SkillsState, on_apply: Callable[[SkillsState], None]) -> None:
        super().__init__(title=_("Habilidades y niveles"), resizable=True)
        block_parent(self, parent)
        self.set_default_size(1180, 780)
        self.state = copy.deepcopy(state)
        self._on_apply = on_apply
        self._current: SkillGroup | None = None
        self._rows: list[SkillRow] = []
        self._loading = False

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self._build_body())
        outer.append(Gtk.Separator())
        outer.append(self._build_buttons())
        self.set_child(outer)
        self._refresh_groups()
        self._select(self.state.groups[0] if self.state.groups else None)

    # --- construcción ----------------------------------------------------------------------------
    def _build_body(self) -> Gtk.Widget:
        body = Gtk.Box(spacing=12, vexpand=True, margin_top=10, margin_bottom=10, margin_start=12, margin_end=12)
        # grupos
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, width_request=230)
        title = Gtk.Label(label=_("Grupos"), xalign=0)
        title.add_css_class("title-4")
        left.append(title)
        self.group_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.group_list.add_css_class("boxed-list")
        self.group_list.connect("row-selected", self._group_selected)
        scroll = wide_scrollbars(Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        scroll.set_child(self.group_list)
        left.append(scroll)
        add_radar = Gtk.Button(label=_("Añadir radar"))
        add_radar.connect("clicked", self._add_radar)
        propose = Gtk.Button(label=_("Proponer radares"), tooltip_text=_(
            "Agrupa por temas las habilidades que ya tienes; luego los puedes editar"))
        propose.connect("clicked", self._propose)
        self.remove_group = Gtk.Button(label=_("Quitar este radar"))
        self.remove_group.connect("clicked", self._remove_group)
        for button in (add_radar, propose, self.remove_group):
            left.append(button)
        self.message = Gtk.Label(xalign=0, wrap=True)
        self.message.add_css_class("dim-label")
        left.append(self.message)
        body.append(left)
        # habilidades del grupo
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        head = Gtk.Box(spacing=8)
        self.group_name = Gtk.Entry(hexpand=True, placeholder_text=_("Nombre del radar (Cloud, Lenguajes…)"))
        self.group_name.connect("changed", self._group_renamed)
        head.append(self.group_name)
        down = Gtk.Button(label=_("−1 a todas"), tooltip_text=_("Baja un punto el nivel de todas las habilidades del grupo"))
        down.connect("clicked", lambda _button: self._shift_all(-1))
        up = Gtk.Button(label=_("+1 a todas"), tooltip_text=_("Sube un punto el nivel de todas las habilidades del grupo"))
        up.connect("clicked", lambda _button: self._shift_all(1))
        head.append(down)
        head.append(up)
        center.append(head)
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("error")
        center.append(self.status)
        self.rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        rows_scroll = wide_scrollbars(Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        rows_scroll.set_child(self.rows_box)
        center.append(rows_scroll)
        adders = Gtk.Box(spacing=8)
        add_skill = Gtk.Button(label=_("Añadir habilidad"))
        add_skill.connect("clicked", lambda _button: self._add_skill(SkillItem("", 5)))
        adders.append(add_skill)
        self.catalog_button = Gtk.MenuButton(label=_("Añadir del catálogo…"), popover=self._build_catalog())
        adders.append(self.catalog_button)
        center.append(adders)
        body.append(center)
        # leyenda y vista previa
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, width_request=340)
        question = Gtk.Label(label=_("¿Me presentaría a una oferta que lo pide como requisito y lo defendería en la "
                                      "entrevista?"), xalign=0, wrap=True)
        question.add_css_class("title-4")
        right.append(question)
        self.level_rows: list[tuple[int, int, Gtk.Box]] = []
        for low, high, title_text, meaning in level_scale():
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            row.add_css_class("level-row")
            label = Gtk.Label(xalign=0, use_markup=True)
            span = f"{low}" if low == high else f"{low}–{high}"
            label.set_markup(f"<b>{span}</b>  {_escape(title_text)}")
            detail = Gtk.Label(label=meaning, xalign=0, wrap=True, max_width_chars=44)
            detail.add_css_class("dim-label")
            row.append(label)
            row.append(detail)
            self.level_rows.append((low, high, row))
            right.append(row)
        self.preview = RadarView()
        self.preview.set_content_height(250)
        right.append(self.preview)
        body.append(right)
        return body

    def _build_buttons(self) -> Gtk.Widget:
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=8, margin_bottom=8, margin_start=16, margin_end=16)
        cancel = Gtk.Button(label=_("Cancelar"))
        cancel.connect("clicked", lambda _button: self.close())
        apply = Gtk.Button(label=_("Aplicar"))
        apply.add_css_class("suggested-action")
        apply.connect("clicked", self._apply)
        buttons.append(cancel)
        buttons.append(apply)
        return buttons

    def _build_catalog(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8, margin_bottom=8, margin_start=8,
                      margin_end=8, width_request=300)
        self.catalog_search = Gtk.SearchEntry(placeholder_text=_("Buscar…"))
        self.catalog_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.catalog_list.set_filter_func(self._catalog_filter)
        self.catalog_list.connect("row-activated", self._catalog_picked)
        self.catalog_search.connect("search-changed", lambda _entry: self.catalog_list.invalidate_filter())
        scroll = Gtk.ScrolledWindow(min_content_height=280, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.catalog_list)
        box.append(self.catalog_search)
        box.append(scroll)
        popover.set_child(box)
        popover.connect("show", lambda _popover: self._fill_catalog())
        self._catalog_specs: dict[Gtk.ListBoxRow, str] = {}
        return popover

    # --- el catálogo -----------------------------------------------------------------------------
    def _fill_catalog(self) -> None:
        """Las habilidades habituales que aún no tienes (técnicas, o blandas si el grupo es el de las blandas)."""
        while (row := self.catalog_list.get_first_child()) is not None:
            self.catalog_list.remove(row)
        self._catalog_specs = {}
        soft = self._current is not None and self._current.kind == SOFT
        have = set()
        for group in self.state.groups:
            if (group.kind == SOFT) == soft:
                for skill in group.skills:
                    have |= aliases(skill.spec)
        for spec in (SOFT_VOCABULARY if soft else DEFAULT_CATALOG):
            names = aliases(spec)
            if not names or names & have or names & {"ingles", "english"}:
                continue
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label=parse_term(spec)[0].capitalize() if soft else parse_term(spec)[0],
                                    xalign=0, margin_top=4, margin_bottom=4, margin_start=6))
            self._catalog_specs[row] = spec
            self.catalog_list.append(row)
        self.catalog_search.set_text("")

    def _catalog_filter(self, row: Gtk.ListBoxRow) -> bool:
        wanted = self.catalog_search.get_text().strip().casefold()
        spec = self._catalog_specs.get(row, "")
        return not wanted or wanted in spec.casefold()

    def _catalog_picked(self, _list, row: Gtk.ListBoxRow) -> None:
        spec = self._catalog_specs.get(row)
        if spec and self._current is not None:
            name, synonyms = split_spec(spec)
            self._add_skill(SkillItem(join_spec(name.capitalize() if self._current.kind == SOFT else name, synonyms), 5))
        self.catalog_button.get_popover().popdown()

    # --- grupos ----------------------------------------------------------------------------------
    def _refresh_groups(self) -> None:
        selected = self._current
        self._loading = True
        while (row := self.group_list.get_first_child()) is not None:
            self.group_list.remove(row)
        self._group_rows: list[tuple[Gtk.ListBoxRow, SkillGroup]] = []
        for group in self.state.groups:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=f"{group.name or _('Radar')} · {len([s for s in group.skills if s.name])}",
                              xalign=0, margin_top=6, margin_bottom=6, margin_start=8, ellipsize=3)
            row.set_child(label)
            self._group_rows.append((row, group))
            self.group_list.append(row)
            if group is selected:
                self.group_list.select_row(row)
        self._loading = False

    def _group_selected(self, _list, row: Gtk.ListBoxRow | None) -> None:
        if self._loading or row is None:
            return
        self._select(next((group for candidate, group in self._group_rows if candidate is row), None))

    def _select(self, group: SkillGroup | None) -> None:
        self._current = group
        self._loading = True
        for row, candidate in self._group_rows:
            if candidate is group:
                self.group_list.select_row(row)
        while (child := self.rows_box.get_first_child()) is not None:
            self.rows_box.remove(child)
        self._rows = []
        radar = group is not None and group.kind == RADAR
        self.group_name.set_visible(radar)
        self.remove_group.set_sensitive(radar)
        self.group_name.set_text(group.name if radar else "")
        if group is not None:
            for item in group.skills:
                self._build_row(item)
        self._loading = False
        self._refresh_status()

    def _group_renamed(self, entry: Gtk.Entry) -> None:
        if self._loading or self._current is None or self._current.kind != RADAR:
            return
        self._current.name = entry.get_text()
        self._refresh_counts()

    def _add_radar(self, _button) -> None:
        group = SkillGroup("", RADAR, [])
        self.state.groups.insert(self._radar_insert_position(), group)
        self._refresh_groups()
        self._select(group)
        self.group_name.grab_focus()

    def _radar_insert_position(self) -> int:
        return max((index + 1 for index, group in enumerate(self.state.groups) if group.kind == RADAR), default=0)

    def _remove_group(self, _button) -> None:
        if self._current is None or self._current.kind != RADAR:
            return
        position = self.state.groups.index(self._current)
        self.state.groups.remove(self._current)
        self._refresh_groups()
        self._select(self.state.groups[min(position, len(self.state.groups) - 1)] if self.state.groups else None)

    def _propose(self, _button) -> None:
        profile = Profile(name="")
        apply_state(self.state, profile)
        existing = {group.name.strip().casefold() for group in self.state.groups if group.kind == RADAR}
        in_radars = set()
        for group in self.state.groups:
            if group.kind == RADAR:
                for skill in group.skills:
                    in_radars |= aliases(skill.spec)
        added = []
        for radar in suggest_radars(profile):
            axes = [axis for axis in radar.axes if not aliases(axis.spec) & in_radars]   # lo que ya está en un radar no se repite
            if radar.name.casefold() in existing or radar.name == other_name() or len(axes) < MIN_AXES:
                continue   # «Otras habilidades» ya es un grupo: lo que sobra se queda ahí
            group = SkillGroup(radar.name, RADAR, [SkillItem(axis.spec, axis.level) for axis in axes])
            self.state.groups.insert(self._radar_insert_position(), group)
            added.append(radar)
        self._refresh_groups()
        if added:
            self.message.set_text(_("Radares propuestos: {names}. Revisa los elementos y los niveles.").format(
                names=", ".join(radar.name for radar in added)))
        else:
            self.message.set_text(_("No hay nada que proponer: añade habilidades (al menos tres de un mismo tema) o ya "
                                    "tienes radares con esos nombres."))

    # --- habilidades -----------------------------------------------------------------------------
    def _build_row(self, item: SkillItem) -> SkillRow:
        row = SkillRow(item, self._skill_changed, self._remove_skill)
        self._rows.append(row)
        self.rows_box.append(row)
        return row

    def _add_skill(self, item: SkillItem) -> None:
        if self._current is None:
            return
        self._current.skills.append(item)
        row = self._build_row(item)
        self._refresh_counts()
        self._refresh_status()
        row.name.grab_focus()

    def _remove_skill(self, row: SkillRow) -> None:
        if self._current is not None and row.item in self._current.skills:
            self._current.skills.remove(row.item)
        self._rows.remove(row)
        self.rows_box.remove(row)
        self._refresh_counts()
        self._refresh_status()

    def _shift_all(self, step: int) -> None:
        for row in self._rows:
            row.set_level(round(row.scale.get_value()) + step)

    def _skill_changed(self, row: SkillRow) -> None:
        self._highlight(round(row.scale.get_value()))
        self._refresh_counts()
        self._refresh_status()

    # --- lo que se ve ----------------------------------------------------------------------------
    def _highlight(self, level: int | None) -> None:
        for low, high, row in self.level_rows:
            if level is not None and low <= level <= high:
                row.add_css_class("level-active")
            else:
                row.remove_css_class("level-active")

    def _refresh_counts(self) -> None:
        for row, group in self._group_rows:
            row.get_child().set_text(f"{group.name or _('Radar')} · {len([s for s in group.skills if s.name])}")

    def _refresh_status(self) -> None:
        group = self._current
        notes = []
        if group is not None and group.kind == RADAR:
            count = len([item for item in group.skills if item.name])
            if count < MIN_AXES or count > MAX_AXES:
                notes.append(_("Un radar necesita entre {low} y {high} habilidades (ahora hay {count}).").format(
                    low=MIN_AXES, high=MAX_AXES, count=count))
        repeated = self.state.duplicates()
        if repeated:
            notes.append(_("Está en más de un grupo: {names}. Se usa la primera vez que aparece.").format(
                names=", ".join(sorted(set(repeated)))))
        self.status.set_text("\n".join(notes))
        skills = [item for item in (group.skills if group else []) if item.name]
        shown = skills[:MAX_AXES] if group is not None and group.kind == RADAR else []
        self.preview.set_visible(bool(shown) and len(shown) >= MIN_AXES)
        self.preview.set_data([item.name for item in shown], [float(item.level) for item in shown], None, Fit.UNKNOWN)

    def _apply(self, _button) -> None:
        self._on_apply(self.state)
        self.close()


def _escape(text: str) -> str:
    from gi.repository import GLib
    return GLib.markup_escape_text(text)
