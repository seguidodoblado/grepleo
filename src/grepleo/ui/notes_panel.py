"""Las notas de una oferta: texto libre que se guarda solo mientras se escribe."""
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..models import Job

SAVE_DELAY_MS = 700   # tras la última tecla


class NotesPanel(Gtk.Box):
    """Un cuadro de texto para la oferta elegida.

    `on_change(job, notes)` se llama al guardar; el panel no sabe nada de la base de datos."""

    def __init__(self, on_change: Callable[[Job, str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._on_change = on_change
        self.job: Job | None = None
        self._loading = False
        self._pending = 0
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=6, right_margin=6, top_margin=4,
                                 bottom_margin=4, accepts_tab=False, vexpand=True)
        self.text.get_buffer().connect("changed", self._text_changed)
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=120, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.text)
        scroll.add_css_class("frame")
        self.append(scroll)
        self.load(None)

    def load(self, job: Job | None) -> None:
        """Muestra las notas de otra oferta (guardando antes las pendientes de la anterior)."""
        self.flush()
        self.job = job
        self._loading = True
        self.text.get_buffer().set_text(job.notes if job else "", -1)
        self.text.set_sensitive(job is not None)
        self._loading = False

    def _notes(self) -> str:
        buffer = self.text.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()

    def _text_changed(self, _buffer) -> None:
        if self._loading or self.job is None:
            return
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(SAVE_DELAY_MS, self._save_later)

    def _save_later(self) -> bool:
        self._pending = 0
        self._save()
        return False

    def _save(self) -> None:
        if self.job is not None:
            self._on_change(self.job, self._notes())

    def flush(self) -> None:
        """Guarda ya lo que esté pendiente (al cambiar de oferta o cerrar la ventana)."""
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
            self._save()
