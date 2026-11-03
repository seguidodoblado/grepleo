"""Editor de un perfil: lo que sabes y lo que buscas."""
import sqlite3
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..i18n import _
from ..profiles import (
    STUDIES,
    Profile,
    format_categories,
    format_languages,
    parse_categories,
    parse_languages,
    split_commas,
    split_lines,
)
from ..storage import Store
from .common import labeled

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


class ProfileWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window, store: Store, profile: Profile | None, identifier: int | None,
                 on_saved: Callable[[int], None]) -> None:
        super().__init__(title=_("Perfil"), transient_for=parent, modal=True)
        self.set_default_size(620, 720)
        self._store = store
        self._identifier = identifier
        self._on_saved = on_saved
        profile = profile or Profile(name="")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16)
        self._name = Gtk.Entry(text=profile.name)
        box.append(labeled(_("Nombre del perfil"), self._name))
        self._headline = Gtk.Entry(text=profile.headline, placeholder_text=_("Por ejemplo: CRM Manager con Salesforce"))
        box.append(labeled(_("Quién eres (cargo actual o resumen)"), self._headline))

        row = Gtk.Box(spacing=12)
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
        box.append(labeled(_("Idiomas (con nivel A1 a C2)"), self._languages))

        scroll, self._must = _text_view("\n".join(profile.must))
        box.append(labeled(_("Imprescindibles: uno por línea; sinónimos con | (Power BI|powerbi)"), scroll))
        scroll, self._nice = _text_view("\n".join(profile.nice))
        box.append(labeled(_("Deseables: uno por línea"), scroll))
        scroll, self._avoid = _text_view("\n".join(profile.avoid), 50)
        box.append(labeled(_("Prefiero que no aparezcan: uno por línea"), scroll))

        modes = Gtk.Box(spacing=12)
        self._modes = {}
        for mode in WORK_MODES:
            check = Gtk.CheckButton(label=work_mode_label(mode), active=mode in profile.work_modes)
            self._modes[mode] = check
            modes.append(check)
        box.append(labeled(_("Modalidades que acepto (ninguna marcada = cualquiera)"), modes))

        self._locations = Gtk.Entry(text=", ".join(profile.locations), placeholder_text=_("Madrid, Pozuelo"))
        box.append(labeled(_("Ubicaciones que me valen (separadas por comas)"), self._locations))

        scroll, self._categories = _text_view(format_categories(profile.categories), 70)
        box.append(labeled(_("Tipos de oferta: «Nombre: palabra, palabra», uno por línea"), scroll))
        scroll, self._notes = _text_view(profile.notes, 60)
        box.append(labeled(_("Notas sobre tu experiencia (para uso futuro)"), scroll))

        self._error = Gtk.Label(xalign=0, wrap=True)
        self._error.add_css_class("error")
        box.append(self._error)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label=_("Cancelar"))
        save = Gtk.Button(label=_("Guardar"))
        save.add_css_class("suggested-action")
        cancel.connect("clicked", lambda _button: self.close())
        save.connect("clicked", self._on_save)
        buttons.append(cancel)
        buttons.append(save)
        box.append(buttons)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(box)
        self.set_child(scrolled)

    def _collect(self) -> Profile:
        return Profile(
            name=self._name.get_text().strip(), headline=self._headline.get_text().strip(),
            years=int(self._years.get_value()), studies=STUDIES[self._studies.get_selected()],
            languages=parse_languages(self._languages.get_text()), must=split_lines(_text_of(self._must)),
            nice=split_lines(_text_of(self._nice)), avoid=split_lines(_text_of(self._avoid)),
            salary_min=int(self._salary.get_value()),
            work_modes=[mode for mode, check in self._modes.items() if check.get_active()],
            locations=split_commas(self._locations.get_text()),
            categories=parse_categories(_text_of(self._categories)), notes=_text_of(self._notes).strip())

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
