"""El seguimiento de una oferta: en qué fase está el proceso, los próximos pasos, el recordatorio y el histórico."""
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..i18n import _
from ..models import EventKind, Job, JobEvent, Stage
from ..storage import Store
from .common import pick_icon
from .date_picker import DatePicker, today

SAVE_DELAY_MS = 700   # tras la última tecla


def _small_button(icons: tuple[str, ...], tooltip: str) -> Gtk.Button:
    return Gtk.Button(icon_name=pick_icon(*icons), tooltip_text=tooltip, valign=Gtk.Align.START,
                      css_classes=["flat"])


class TrackingPanel(Gtk.Box):
    """Fase del proceso, recordatorio, próximos pasos y una lista con lo que ha ido ocurriendo.

    Los cambios se guardan solos; `on_change(job)` avisa a la ventana para que repinte la tabla."""

    def __init__(self, store: Store, on_change: Callable[[Job], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._store = store
        self._on_change = on_change
        self.job: Job | None = None
        self._loading = False
        self._pending = 0
        self._editing: int | None = None

        top = Gtk.Box(spacing=8)
        top.append(Gtk.Label(label=_("Fase del proceso")))
        self.stage = Gtk.DropDown.new_from_strings([stage.label for stage in Stage])
        self.stage.set_hexpand(True)
        self.stage.connect("notify::selected", lambda *_args: self._save_tracking())
        top.append(self.stage)
        self.append(top)

        reminder = Gtk.Box(spacing=8)
        reminder.append(Gtk.Label(label=_("Recordar el")))
        self.reminder = DatePicker(lambda _day: self._save_tracking())
        reminder.append(self.reminder)
        self.append(reminder)

        steps_label = Gtk.Label(label=_("Próximos pasos"), xalign=0)
        steps_label.add_css_class("heading")
        self.append(steps_label)
        self.steps = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=6, right_margin=6, top_margin=4,
                                  bottom_margin=4, accepts_tab=False)
        self.steps.get_buffer().connect("changed", self._steps_changed)
        steps_scroll = Gtk.ScrolledWindow(min_content_height=64, max_content_height=120,
                                          propagate_natural_height=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        steps_scroll.set_child(self.steps)
        steps_scroll.add_css_class("frame")
        self.append(steps_scroll)

        history_label = Gtk.Label(label=_("Histórico"), xalign=0, margin_top=6)
        history_label.add_css_class("heading")
        self.append(history_label)
        form = Gtk.Box(spacing=6)
        self.day = DatePicker(lambda _day: None, clearable=False, shortcuts=False)
        form.append(self.day)
        self.kind = Gtk.DropDown.new_from_strings([kind.label for kind in EventKind])
        form.append(self.kind)
        self.append(form)
        entry_row = Gtk.Box(spacing=6)
        self.text = Gtk.Entry(hexpand=True, placeholder_text=_("Qué ha pasado: con quién, qué piden, qué te dijeron…"))
        self.text.connect("activate", self._submit)
        entry_row.append(self.text)
        self.submit_button = Gtk.Button(label=_("Añadir"))
        self.submit_button.connect("clicked", self._submit)
        entry_row.append(self.submit_button)
        self.cancel_button = Gtk.Button(label=_("Cancelar"))
        self.cancel_button.connect("clicked", lambda _button: self._stop_editing())
        entry_row.append(self.cancel_button)
        self.append(entry_row)

        self.events = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.events.add_css_class("boxed-list")
        self.empty = Gtk.Label(label=_("Aún no hay nada apuntado."), xalign=0, margin_top=4)
        self.empty.add_css_class("dim-label")
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=120, hscrollbar_policy=Gtk.PolicyType.NEVER)
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        holder.append(self.events)
        holder.append(self.empty)
        scroll.set_child(holder)
        self.append(scroll)
        self.load(None)

    # --- cargar y guardar --------------------------------------------------------------------------
    def load(self, job: Job | None) -> None:
        """Muestra el seguimiento de otra oferta (guardando antes lo pendiente de la anterior)."""
        self.flush()
        self.job = job
        self._loading = True
        stages = list(Stage)
        self.stage.set_selected(stages.index(Stage(job.stage)) if job and job.stage in {s.value for s in stages}
                                else 0)
        self.reminder.set_day(job.remind_on if job else "")
        self.steps.get_buffer().set_text(job.next_steps if job else "", -1)
        for widget in (self.stage, self.reminder, self.steps, self.day, self.kind, self.text, self.submit_button):
            widget.set_sensitive(job is not None)
        self._loading = False
        self._stop_editing()
        self._reload_events()

    def _steps(self) -> str:
        buffer = self.steps.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()

    def _steps_changed(self, _buffer) -> None:
        if self._loading or self.job is None:
            return
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(SAVE_DELAY_MS, self._save_later)

    def _save_later(self) -> bool:
        self._pending = 0
        self._save_tracking()
        return False

    def _save_tracking(self) -> None:
        if self._loading or self.job is None:
            return
        job = self.job
        job.stage = list(Stage)[self.stage.get_selected()].value
        job.next_steps = self._steps()
        job.remind_on = self.reminder.day
        self._store.set_tracking(job.key, job.stage, job.next_steps, job.remind_on)
        self._on_change(job)

    def flush(self) -> None:
        """Guarda ya lo que esté pendiente (al cambiar de oferta o cerrar la ventana)."""
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
            self._save_tracking()

    # --- histórico ---------------------------------------------------------------------------------
    def _reload_events(self) -> None:
        while (row := self.events.get_first_child()) is not None:
            self.events.remove(row)
        events = self._store.list_events(self.job.key) if self.job else []
        for event in events:
            self.events.append(self._row(event))
        self.events.set_visible(bool(events))
        self.empty.set_visible(not events)

    def _row(self, event: JobEvent) -> Gtk.Widget:
        box = Gtk.Box(spacing=8, margin_top=6, margin_bottom=6, margin_start=8, margin_end=4)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        head = Gtk.Label(xalign=0)
        head.set_markup(f"<b>{GLib.markup_escape_text(event.day)}</b> · {GLib.markup_escape_text(event.kind.label)}")
        info.append(head)
        if event.text:
            info.append(Gtk.Label(label=event.text, xalign=0, wrap=True, selectable=True))
        box.append(info)
        edit = _small_button(("document-edit", "text-editor"), _("Editar"))
        edit.connect("clicked", lambda _button, e=event: self._start_editing(e))
        delete = _small_button(("user-trash", "edit-delete"), _("Borrar"))
        delete.connect("clicked", lambda _button, e=event: self._delete(e))
        box.append(edit)
        box.append(delete)
        return box

    def _start_editing(self, event: JobEvent) -> None:
        self._editing = event.id
        self.day.set_day(event.day)
        self.kind.set_selected(list(EventKind).index(event.kind))
        self.text.set_text(event.text)
        self.submit_button.set_label(_("Guardar cambio"))
        self.cancel_button.set_visible(True)
        self.text.grab_focus()

    def _stop_editing(self) -> None:
        self._editing = None
        self.day.set_day(today().isoformat())
        self.kind.set_selected(0)
        self.text.set_text("")
        self.submit_button.set_label(_("Añadir"))
        self.cancel_button.set_visible(False)

    def _submit(self, *_args) -> None:
        if self.job is None:
            return
        day = self.day.day or today().isoformat()
        kind = list(EventKind)[self.kind.get_selected()]
        text = self.text.get_text().strip()
        if self._editing is None:
            self._store.add_event(self.job.key, day, kind, text)
        else:
            self._store.update_event(self._editing, day, kind, text)
        self._stop_editing()
        self._events_changed()

    def _delete(self, event: JobEvent) -> None:
        self._store.delete_event(event.id)
        if self._editing == event.id:
            self._stop_editing()
        self._events_changed()

    def _events_changed(self) -> None:
        if self.job is None:
            return
        self._reload_events()
        self.job.event_count = len(self._store.list_events(self.job.key))
        self._on_change(self.job)
