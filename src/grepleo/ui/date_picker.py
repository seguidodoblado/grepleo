"""Un selector de fecha pequeño: un botón con la fecha que abre un calendario y atajos."""
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..i18n import _
from .common import icon_button


def today() -> date:
    """El día de hoy en la zona horaria de la persona."""
    return datetime.now(timezone.utc).astimezone().date()


class DatePicker(Gtk.Box):
    """La fecha se guarda como «AAAA-MM-DD» (vacía = sin fecha). `on_changed(day)` se llama al elegirla o quitarla."""

    def __init__(self, on_changed: Callable[[str], None], clearable: bool = True, shortcuts: bool = True) -> None:
        super().__init__(spacing=6)
        self._on_changed = on_changed
        self._loading = False
        self.day = ""
        self.calendar = Gtk.Calendar()
        self._signal = self.calendar.connect("day-selected", self._calendar_selected)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6,
                          margin_start=6, margin_end=6)
        if shortcuts:
            quick = Gtk.Box(spacing=4)
            for label, days in ((_("Mañana"), 1), (_("En 3 días"), 3), (_("En una semana"), 7)):
                button = Gtk.Button(label=label)
                button.connect("clicked", lambda _button, n=days: self.choose(today() + timedelta(days=n)))
                quick.append(button)
            content.append(quick)
        content.append(self.calendar)
        self.popover = Gtk.Popover(child=content)
        self.button = Gtk.MenuButton(popover=self.popover, label=_("Sin fecha"))
        self.append(self.button)
        self.clear_button = None
        if clearable:
            self.clear_button = icon_button(("edit-clear", "edit-delete"), _("Quitar"))
            self.clear_button.connect("clicked", lambda _button: self.set_day("", notify=True))
            self.append(self.clear_button)
        self.set_day("")

    def set_day(self, day: str, notify: bool = False) -> None:
        self.day = day
        self.button.set_label(day or _("Sin fecha"))
        if self.clear_button is not None:
            self.clear_button.set_sensitive(bool(day))
        if day:
            year, month, number = (int(part) for part in day.split("-"))
            self.calendar.handler_block(self._signal)
            self.calendar.select_day(GLib.DateTime.new_local(year, month, number, 0, 0, 0))
            self.calendar.handler_unblock(self._signal)
        if notify:
            self._on_changed(day)

    def choose(self, day: date) -> None:
        self.popover.popdown()
        self.set_day(day.isoformat(), notify=True)

    def _calendar_selected(self, calendar) -> None:
        chosen = calendar.get_date()
        self.choose(date(chosen.get_year(), chosen.get_month(), chosen.get_day_of_month()))
