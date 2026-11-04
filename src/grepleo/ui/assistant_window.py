"""La ventana del asistente de IA: un terminal con tu propia CLI y, debajo, lo que hacer con el CV que genere."""
import os
import re
import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gio, GLib, Gtk, Pango

from ..assistant import Workspace, shell_argv
from ..cv import markdown_to_html
from ..i18n import _
from ..models import Job
from .common import icon_button

TERMINAL_FONT = "Ubuntu Sans Mono, Monospace"   # tipografía del terminal; la segunda es el respaldo
TERMINAL_FONT_SIZE = 11
CHECK_MS = 1500                                  # cada cuánto se mira si ya existe el CV generado
TERMINATE_AFTER_MS = (1500, 4000)                # al cerrar: SIGTERM a los 1,5 s y SIGKILL a los 4 s si la CLI sigue viva


def _signal_session_leader(pid: int, sig: int) -> bool:
    """Manda `sig` al proceso si sigue siendo el líder de la sesión que lanzó el terminal (así no se toca un proceso
    ajeno si el número se reutilizó). Siempre False: es un temporizador de una sola vez."""
    try:
        if os.getsid(pid) == pid:
            os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass   # ya ha salido
    return False


class AssistantWindow(Gtk.Window):
    """Una sesión de tu CLI de IA en un terminal embebido, con la carpeta de la oferta como directorio de trabajo."""

    def __init__(self, parent: Gtk.Window, workspace: Workspace, argv: list[str], job: Job) -> None:
        super().__init__(title=_("Asistente de IA · CV adaptado"), transient_for=parent, resizable=True)
        gi.require_version("Vte", "3.91")
        from gi.repository import Vte
        self.set_default_size(960, 700)
        self._workspace = workspace
        self._job = job
        self._pid = 0   # el proceso de la CLI mientras viva: es líder de su propia sesión
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8, margin_bottom=8,
                      margin_start=8, margin_end=8)
        note = Gtk.Label(xalign=0, wrap=True, label=_(
            "Sesión de «{command}» con tu propia cuenta. Revisa cada permiso que te pida: esta aplicación no ve tus "
            "credenciales. Cuando termine, el CV adaptado debe estar en «{output}».").format(
                command=argv[0], output=workspace.output))
        box.append(note)
        self.terminal = Vte.Terminal(vexpand=True, hexpand=True)
        font = Pango.FontDescription()
        font.set_family(TERMINAL_FONT)
        font.set_weight(Pango.Weight.NORMAL)
        font.set_size(TERMINAL_FONT_SIZE * Pango.SCALE)
        self.terminal.set_font(font)
        self.terminal.set_scrollback_lines(10000)
        self.terminal.connect("child-exited", self._child_exited)
        box.append(self.terminal)

        bar = Gtk.Box(spacing=8)
        self.status = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.status.add_css_class("dim-label")
        bar.append(self.status)
        self.folder_button = icon_button(("folder-open", "document-open"), _("Abrir carpeta"))
        self.folder_button.connect("clicked", self._open_folder)
        bar.append(self.folder_button)
        self.save_button = icon_button(("document-save-as", "document-save"), _("Guardar CV como…"))
        self.save_button.connect("clicked", self._save_as)
        bar.append(self.save_button)
        box.append(bar)
        self.set_child(box)
        self._refresh(False)
        self._timer = GLib.timeout_add(CHECK_MS, self._tick)
        self.connect("close-request", self._on_close)
        # child_setup y child_setup_data quedan a None; -1 = sin límite de tiempo; sin cancelable.
        self.terminal.spawn_async(Vte.PtyFlags.DEFAULT, str(workspace.folder), shell_argv(argv), None,
                                  GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None, self._spawned)
        self.terminal.grab_focus()

    # --- ciclo de vida -----------------------------------------------------------------------------
    def _spawned(self, _terminal, pid, error, *_data) -> None:
        if error is None:
            self._pid = pid
        else:
            self.status.set_text(_("No se pudo lanzar el asistente: {error_message}").format(
                error_message=error.message))

    def _tick(self) -> bool:
        self._refresh(False)
        return True

    def _child_exited(self, _terminal, _status) -> None:
        self._pid = 0
        self._refresh(True)

    def _on_close(self, *_args) -> bool:
        GLib.source_remove(self._timer)
        self._terminate()
        return False

    def _terminate(self) -> None:
        """La CLI recibe SIGHUP al destruirse el terminal, pero una CLI interactiva puede ignorarlo: si sigue viva se le
        manda SIGTERM y, si aun así no sale, SIGKILL, para que no quede un proceso suelto tras cerrar la ventana."""
        pid = self._pid
        self._pid = 0
        if not pid:
            return
        for delay, sig in zip(TERMINATE_AFTER_MS, (signal.SIGTERM, signal.SIGKILL), strict=True):
            GLib.timeout_add(delay, _signal_session_leader, pid, sig)

    def _output(self):
        return self._workspace.folder / self._workspace.output

    def _refresh(self, exited: bool) -> None:
        ready = self._output().is_file()
        self.save_button.set_sensitive(ready)
        if ready:
            self.status.set_text(_("CV adaptado listo: «{name}».").format(name=self._workspace.output))
        elif exited:
            self.status.set_text(_("La sesión ha terminado y no se ha creado «{name}».").format(
                name=self._workspace.output))
        else:
            self.status.set_text(_("Esperando a que el asistente cree «{name}»…").format(name=self._workspace.output))

    # --- qué hacer con el resultado ----------------------------------------------------------------
    def _open_folder(self, _button) -> None:
        Gtk.FileLauncher.new(Gio.File.new_for_path(str(self._workspace.folder))).launch(self, None, None)

    def _suggested_name(self) -> str:
        base = re.sub(r"[^A-Za-z0-9._-]+", "-", f"cv-{self._job.company or self._job.title}").strip("-.")
        return f"{base[:60] or 'cv'}.md"

    def _save_as(self, _button) -> None:
        dialog = Gtk.FileDialog(title=_("Guardar CV como…"), initial_name=self._suggested_name())
        filters = Gio.ListStore.new(Gtk.FileFilter)
        for name, pattern in ((_("Markdown (.md)"), "*.md"), (_("Página web para imprimir o guardar en PDF (.html)"),
                                                              "*.html")):
            file_filter = Gtk.FileFilter(name=name)
            file_filter.add_pattern(pattern)
            filters.append(file_filter)
        dialog.set_filters(filters)
        dialog.save(self, None, self._saved)

    def _saved(self, dialog, result) -> None:
        try:
            target = dialog.save_finish(result)
        except GLib.Error:
            return   # cancelado
        path = target.get_path() or ""
        try:
            markdown = self._output().read_text(encoding="utf-8")
            text = markdown_to_html(markdown, self._job.title) if path.lower().endswith((".html", ".htm")) else markdown
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as error:
            self.status.set_text(_("No se pudo guardar el CV: {error}").format(error=error))
            return
        self.status.set_text(_("CV guardado en {path}.").format(path=path))
