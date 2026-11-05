"""Editor de un perfil: lo que sabes y lo que buscas."""
import sqlite3
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from ..i18n import _
from ..links import DOMAIN_MISMATCH, PLATFORMS, normalize_link
from ..profiles import (
    STUDIES,
    Profile,
    bare_levels,
    format_categories,
    format_languages,
    parse_categories,
    parse_languages,
    split_commas,
    split_lines,
)
from ..skills_edit import apply_state, state_from_profile
from ..storage import Store
from .common import block_parent, labeled, link_icon, pick_icon
from .skills_window import SkillsWindow

WORK_MODES = ("remote", "hybrid", "onsite")


def studies_labels() -> list[str]:
    return [_("Sin indicar"), _("FP"), _("Grado"), _("Máster")]


def work_mode_label(mode: str) -> str:
    return {"remote": _("Remoto"), "hybrid": _("Híbrido"), "onsite": _("Presencial")}[mode]


def _text_view(content: str, height: int = 80) -> tuple[Gtk.ScrolledWindow, Gtk.TextView]:
    view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=6, bottom_margin=6, left_margin=6, right_margin=6)
    view.get_buffer().set_text(content)
    scroll = Gtk.ScrolledWindow(min_content_height=height, has_frame=True)
    scroll.set_child(view)
    return scroll, view


def _text_of(view: Gtk.TextView) -> str:
    buffer = view.get_buffer()
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)


def _section(title: str) -> Gtk.Label:
    label = Gtk.Label(label=title, xalign=0, margin_top=10)
    label.add_css_class("title-4")
    return label


def _columns(*columns: Gtk.Widget) -> Gtk.Box:
    """Varias columnas del mismo ancho que crecen con la ventana."""
    row = Gtk.Box(spacing=12, homogeneous=True, vexpand=True)
    for column in columns:
        column.set_vexpand(True)
        row.append(column)
    return row


def _grown(widget: Gtk.Widget) -> Gtk.Widget:
    widget.set_vexpand(True)
    return widget


class ProfileWindow(Gtk.Window):
    """El editor del perfil: una ventana que se puede maximizar, con sus campos en secciones."""

    def __init__(self, parent: Gtk.Window, store: Store, profile: Profile | None, identifier: int | None,
                 on_saved: Callable[[int], None]) -> None:
        super().__init__(title=_("Perfil"), resizable=True)
        block_parent(self, parent)
        self.set_default_size(980, 780)
        self._store = store
        self._identifier = identifier
        self._on_saved = on_saved
        profile = profile or Profile(name="")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12, margin_bottom=12,
                      margin_start=16, margin_end=16, vexpand=True)
        box.append(_section(_("Quién eres")))
        self._name = Gtk.Entry(text=profile.name)
        self._headline = Gtk.Entry(text=profile.headline, placeholder_text=_("Por ejemplo: CRM Manager con Salesforce"),
                                   hexpand=True)
        who = Gtk.Box(spacing=12, homogeneous=True)
        who.append(labeled(_("Nombre del perfil"), self._name))
        who.append(labeled(_("Quién eres (cargo actual o resumen)"), self._headline))
        box.append(who)

        row = Gtk.Box(spacing=12, homogeneous=True)
        self._years = Gtk.SpinButton.new_with_range(0, 50, 1)
        self._years.set_value(profile.years)
        row.append(labeled(_("Años de experiencia"), self._years))
        self._studies = Gtk.DropDown.new_from_strings(studies_labels())
        self._studies.set_selected(STUDIES.index(profile.studies))
        row.append(labeled(_("Estudios"), self._studies))
        self._salary = Gtk.SpinButton.new_with_range(0, 500000, 1000)
        self._salary.set_value(profile.salary_min)
        row.append(labeled(_("Salario mínimo bruto anual (€, 0 = no importa)"), self._salary))
        box.append(row)
        self._languages = Gtk.Entry(text=format_languages(profile.languages),
                                    placeholder_text=_("Por ejemplo: Inglés C1, Francés B1"))
        self._languages.connect("changed", self._languages_changed)
        self._languages_warning = Gtk.Label(xalign=0, wrap=True, visible=False)
        self._languages_warning.add_css_class("error")
        languages_box = labeled(_("Idiomas (con nivel A1 a C2)"), self._languages)
        languages_box.append(self._languages_warning)
        box.append(languages_box)
        self._languages_changed(self._languages)

        box.append(_section(_("Habilidades y niveles")))
        skills_hint = Gtk.Label(xalign=0, wrap=True, label=_(
            "Tus habilidades técnicas y blandas, cada una con un nivel de 0 a 10 y con los radares por temas que se "
            "comparan con lo que pide cada oferta. Se editan en una ventana aparte, con la escala de niveles a la vista."))
        skills_hint.add_css_class("dim-label")
        box.append(skills_hint)
        self._skills = state_from_profile(profile)
        skills_row = Gtk.Box(spacing=12)
        self._skills_summary = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        edit_skills = Gtk.Button(label=_("Editar habilidades y niveles…"))
        edit_skills.add_css_class("suggested-action")
        edit_skills.connect("clicked", self._edit_skills)
        skills_row.append(self._skills_summary)
        skills_row.append(edit_skills)
        box.append(skills_row)
        self._refresh_skills_summary()

        box.append(_section(_("Qué buscas")))
        scroll, self._avoid = _text_view("\n".join(profile.avoid), 60)
        modes = Gtk.Box(spacing=12)
        self._modes = {}
        for mode in WORK_MODES:
            check = Gtk.CheckButton(label=work_mode_label(mode), active=mode in profile.work_modes)
            self._modes[mode] = check
            modes.append(check)
        self._locations = Gtk.Entry(text=", ".join(profile.locations), placeholder_text=_("Madrid, Pozuelo"))
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.append(labeled(_("Modalidades que acepto (ninguna marcada = cualquiera)"), modes))
        left.append(labeled(_("Ubicaciones que me valen (separadas por comas)"), self._locations))
        box.append(_columns(left, labeled(_("Prefiero que no aparezcan: uno por línea"), _grown(scroll))))

        box.append(_section(_("Tipos de oferta y notas")))
        scroll_categories, self._categories = _text_view(format_categories(profile.categories), 70)
        scroll_notes, self._notes = _text_view(profile.notes, 70)
        box.append(_columns(labeled(_("Tipos de oferta: «Nombre: palabra, palabra», uno por línea"),
                                    _grown(scroll_categories)),
                            labeled(_("Notas sobre tu experiencia (para uso futuro)"), _grown(scroll_notes))))

        box.append(_section(_("Currículum")))
        hint = Gtk.Label(label=_("Con estos datos se construye tu currículum base y se adapta a cada oferta con tu "
                                 "propia IA. Todo se queda en tu equipo: solo sale si lanzas el asistente."),
                         xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        box.append(hint)
        self._full_name = Gtk.Entry(text=profile.full_name, hexpand=True)
        self._email = Gtk.Entry(text=profile.email, hexpand=True)
        self._phone = Gtk.Entry(text=profile.phone, hexpand=True)
        contact = Gtk.Box(spacing=12, homogeneous=True)
        contact.append(labeled(_("Nombre completo"), self._full_name))
        contact.append(labeled(_("Correo"), self._email))
        contact.append(labeled(_("Teléfono"), self._phone))
        box.append(contact)
        networks_hint = Gtk.Label(xalign=0, wrap=True, label=_(
            "Tus perfiles profesionales: basta el nombre de usuario o pegar la dirección, que se limpia sola."))
        networks_hint.add_css_class("dim-label")
        box.append(networks_hint)
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, column_homogeneous=False)
        self._networks: dict[str, Gtk.Entry] = {}
        for index, platform in enumerate(PLATFORMS):
            row, offset = divmod(index, 2)
            column = offset * 4
            grid.attach(Gtk.Image(icon_name=link_icon(platform.id)), column, row, 1, 1)
            grid.attach(Gtk.Label(label=platform.label, xalign=0), column + 1, row, 1, 1)
            entry = Gtk.Entry(text=profile.networks.get(platform.id, ""), placeholder_text=platform.hint,
                              hexpand=True, width_chars=22)
            entry.connect("changed", self._network_changed, platform.id)
            leave = Gtk.EventControllerFocus()
            leave.connect("leave", lambda _controller, pid=platform.id: self._tidy_network(pid))
            entry.add_controller(leave)
            self._networks[platform.id] = entry
            grid.attach(entry, column + 2, row, 1, 1)
            if offset == 0:
                grid.attach(Gtk.Box(width_request=16), column + 3, row, 1, 1)   # separación entre las dos columnas
            self._network_changed(entry, platform.id)
        box.append(grid)
        scroll_links, self._links = _text_view(profile.links, 64)
        box.append(labeled(_("Otros enlaces: uno por línea"), scroll_links))
        scroll_experience, self._experience = _text_view(profile.experience, 150)
        scroll_education, self._education = _text_view(profile.education, 150)
        box.append(_columns(
            labeled(_("Experiencia profesional: puestos, empresas, fechas y logros"), _grown(scroll_experience)),
            labeled(_("Formación: centros, titulaciones y cursos"), _grown(scroll_education))))
        self._cv_file = profile.cv_file
        upload = Gtk.Box(spacing=8)
        self._cv_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        choose = Gtk.Button(label=_("Elegir mi CV…"))
        choose.connect("clicked", self._choose_cv)
        forget = Gtk.Button(label=_("Quitar"))
        forget.connect("clicked", lambda _button: self._set_cv_file(""))
        for widget in (self._cv_label, choose, forget):
            upload.append(widget)
        box.append(labeled(_("Un CV que ya tengas (PDF, Word o texto): se le pasa a la IA junto al construido arriba"),
                           upload))
        self._set_cv_file(profile.cv_file)

        self._error = Gtk.Label(xalign=0, wrap=True)
        self._error.add_css_class("error")
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=8, margin_bottom=8, margin_start=16,
                          margin_end=16)
        cancel = Gtk.Button(label=_("Cancelar"))
        save = Gtk.Button(label=_("Guardar"))
        save.add_css_class("suggested-action")
        cancel.connect("clicked", lambda _button: self.close())
        save.connect("clicked", self._on_save)
        buttons.append(self._error)
        buttons.append(cancel)
        buttons.append(save)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_child(box)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(scrolled)
        outer.append(Gtk.Separator())
        outer.append(buttons)   # los botones siempre a la vista, aunque la ventana sea pequeña
        self.set_child(outer)

    def _refresh_skills_summary(self) -> None:
        technical = [group for group in self._skills.groups if group.kind != "soft"]
        count = sum(len([item for item in group.skills if item.name]) for group in technical)
        soft = sum(len([item for item in group.skills if item.name]) for group in self._skills.groups
                   if group.kind == "soft")
        radars = len([group for group in self._skills.groups if group.kind == "radar"])
        self._skills_summary.set_text(_("{technical} habilidades técnicas, {soft} blandas y {radars} radares por temas.")
                                      .format(technical=count, soft=soft, radars=radars))

    def _edit_skills(self, _button: Gtk.Button) -> None:
        def applied(state) -> None:
            self._skills = state
            self._refresh_skills_summary()

        SkillsWindow(self, self._skills, applied).present()

    def _languages_changed(self, entry: Gtk.Entry) -> None:
        """Avisa si se escribe un nivel suelto («A2»): se tomaría por un idioma y las ofertas que piden inglés saldrían como
        un requisito que no tienes."""
        levels = bare_levels(entry.get_text())
        self._languages_warning.set_visible(bool(levels))
        if levels:
            self._languages_warning.set_text(_("«{level}» es un nivel, no un idioma: escribe, por ejemplo, «Inglés {level}».")
                                             .format(level=levels[0].strip().upper()))

    def _network_changed(self, entry: Gtk.Entry, platform_id: str) -> None:
        """Avisa con un icono en la casilla si lo escrito no es de esa plataforma (un LinkedIn pegado en la de GitHub)."""
        _value, problem = normalize_link(platform_id, entry.get_text())
        if problem == DOMAIN_MISMATCH:
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, pick_icon("dialog-warning"))
            entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY,
                                        _("Esta dirección no es de {platform}.").format(
                                            platform=next(p.label for p in PLATFORMS if p.id == platform_id)))
        else:
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, None)

    def _tidy_network(self, platform_id: str) -> None:
        """Al salir de la casilla se deja la dirección limpia (sin https://, www., parámetros…)."""
        entry = self._networks[platform_id]
        value, _problem = normalize_link(platform_id, entry.get_text())
        if value != entry.get_text():
            entry.set_text(value)

    def _set_cv_file(self, path: str) -> None:
        self._cv_file = path
        self._cv_label.set_text(path or _("Ninguno"))
        self._cv_label.set_tooltip_text(path or None)

    def _choose_cv(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title=_("Elegir mi CV…"))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        documents = Gtk.FileFilter(name=_("Documentos (PDF, Word, texto)"))
        for pattern in ("*.pdf", "*.doc", "*.docx", "*.odt", "*.txt", "*.md"):
            documents.add_pattern(pattern)
        filters.append(documents)
        dialog.set_filters(filters)
        dialog.open(self, None, self._cv_chosen)

    def _cv_chosen(self, dialog, result) -> None:
        try:
            chosen = dialog.open_finish(result)
        except GLib.Error:
            return   # cancelado
        self._set_cv_file(chosen.get_path() or "")

    def _collect(self) -> Profile:
        profile = self._collect_fields()
        apply_state(self._skills, profile)   # las habilidades, sus niveles y los radares vienen de la ventana «Habilidades»
        return profile

    def _collect_fields(self) -> Profile:
        return Profile(
            name=self._name.get_text().strip(), headline=self._headline.get_text().strip(),
            years=int(self._years.get_value()), studies=STUDIES[self._studies.get_selected()],
            languages=parse_languages(self._languages.get_text()), avoid=split_lines(_text_of(self._avoid)),
            salary_min=int(self._salary.get_value()),
            work_modes=[mode for mode, check in self._modes.items() if check.get_active()],
            locations=split_commas(self._locations.get_text()),
            categories=parse_categories(_text_of(self._categories)), notes=_text_of(self._notes).strip(),
            full_name=self._full_name.get_text().strip(), email=self._email.get_text().strip(),
            phone=self._phone.get_text().strip(), links="\n".join(split_lines(_text_of(self._links))),
            networks={pid: value for pid, entry in self._networks.items()
                      if (value := normalize_link(pid, entry.get_text())[0])},
            experience=_text_of(self._experience).strip(), education=_text_of(self._education).strip(),
            cv_file=self._cv_file)

    def _on_save(self, _button: Gtk.Button) -> None:
        profile = self._collect()
        if not profile.name:
            self._error.set_text(_("El perfil necesita un nombre."))
            return
        try:
            identifier = self._store.save_profile(profile, self._identifier)
        except sqlite3.IntegrityError:
            self._error.set_text(_("Ya existe un perfil con ese nombre."))
            return
        self.close()
        self._on_saved(identifier)
