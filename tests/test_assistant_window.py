import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
    if "3.91" not in gi.Repository.get_default().enumerate_versions("Vte"):
        pytest.skip("sin el terminal embebido (gir1.2-vte-3.91)", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from gi.repository import Gio

from grepleo.assistant import OUTPUT_NAME, Workspace
from grepleo.models import Job
from grepleo.ui.assistant_window import AssistantWindow


def make_window(tmp_path):
    workspace = Workspace(tmp_path, "oferta.md", "cv-base.md", "", OUTPUT_NAME)
    job = Job(key="x:1", source="x", title="DevOps Engineer", company="ACME S.L.")
    return AssistantWindow(Gtk.Window(), workspace, ["true"], job), workspace


class FakeDialog:
    def __init__(self, path):
        self._file = Gio.File.new_for_path(str(path))

    def save_finish(self, _result):
        return self._file


def test_the_window_waits_for_the_cv_and_enables_saving_once_it_exists(tmp_path):
    window, _workspace = make_window(tmp_path)
    assert not window.save_button.get_sensitive() and "Esperando" in window.status.get_text()
    window._refresh(True)
    assert "no se ha creado" in window.status.get_text()
    (tmp_path / OUTPUT_NAME).write_text("# Ana\n\n## Resumen\nDevOps", encoding="utf-8")
    window._refresh(False)
    assert window.save_button.get_sensitive() and "CV adaptado listo" in window.status.get_text()
    assert window._suggested_name() == "cv-ACME-S.L.md"
    window.close()


def test_saving_writes_markdown_as_is_and_html_for_a_web_page(tmp_path):
    window, _workspace = make_window(tmp_path)
    (tmp_path / OUTPUT_NAME).write_text("# Ana\n- uno", encoding="utf-8")
    markdown_target, html_target = tmp_path / "salida.md", tmp_path / "salida.html"
    window._saved(FakeDialog(markdown_target), None)
    window._saved(FakeDialog(html_target), None)
    assert markdown_target.read_text(encoding="utf-8") == "# Ana\n- uno"
    page = html_target.read_text(encoding="utf-8")
    assert "<h1>Ana</h1>" in page and "<li>uno</li>" in page and "DevOps Engineer" in page
    assert "CV guardado en" in window.status.get_text()
    window.close()


def test_closing_the_window_ends_a_cli_that_ignores_hangup_and_terminate(monkeypatch):
    import os
    import time

    from gi.repository import GLib

    from grepleo.ui import assistant_window
    monkeypatch.setattr(assistant_window, "TERMINATE_AFTER_MS", (200, 600))
    workspace = Workspace(__import__("pathlib").Path("/tmp"), "oferta.md", "cv-base.md", "", OUTPUT_NAME)
    job = Job(key="x:1", source="x", title="DevOps")
    window = AssistantWindow(Gtk.Window(), workspace, ["sh", "-c", "trap '' HUP TERM; exec sleep 61.3"], job)
    window.present()                                            # gtk_window_close solo actúa sobre una ventana ya realizada
    context = GLib.MainContext.default()
    deadline = time.monotonic() + 5
    while not window._pid and time.monotonic() < deadline:      # espera a que el terminal lance el proceso
        context.iteration(False)
        time.sleep(0.01)
    pid = window._pid
    assert pid and os.getsid(pid) == pid
    window.close()
    deadline = time.monotonic() + 6
    alive = True
    while alive and time.monotonic() < deadline:
        context.iteration(False)
        time.sleep(0.02)
        try:
            os.kill(pid, 0)
            with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
                alive = handle.read().split(") ")[-1].split()[0] != "Z"     # un zombi ya ha terminado
        except (ProcessLookupError, FileNotFoundError):
            alive = False
    assert not alive, "la CLI que ignora SIGHUP y SIGTERM debe terminar con SIGKILL"


def test_a_signal_is_only_sent_to_the_session_leader_and_never_to_a_missing_process():
    from grepleo.ui.assistant_window import _signal_session_leader
    assert _signal_session_leader(2_000_000_000, 15) is False          # un pid que no existe: no falla
    import os
    assert _signal_session_leader(os.getpid(), 15) is False            # el de pytest no es líder de su sesión: no se toca


def _pump(context, seconds, until=lambda: False):
    import time
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not until():
        context.iteration(False)
        time.sleep(0.01)


def _open(argv, monkeypatch=None):
    from grepleo.ui import assistant_window
    if monkeypatch is not None:
        monkeypatch.setattr(assistant_window, "TERMINATE_AFTER_MS", (200, 600))
    import pathlib
    workspace = Workspace(pathlib.Path("/tmp"), "oferta.md", "cv-base.md", "", OUTPUT_NAME)
    window = AssistantWindow(Gtk.Window(), workspace, argv, Job(key="x:1", source="x", title="DevOps"))
    window.present()
    from gi.repository import GLib
    context = GLib.MainContext.default()
    _pump(context, 5, lambda: bool(window._pid))
    return window, context


def test_closing_with_a_live_cli_hides_the_window_and_only_destroys_it_once_the_cli_has_exited(monkeypatch):
    import os
    window, context = _open(["sh", "-c", "trap '' HUP TERM; exec sleep 61.7"], monkeypatch)
    pid = window._pid
    assert pid and os.getsid(pid) == pid
    window.close()
    # no se destruye aún: el terminal sigue con su proceso y un «child-exited» tardío no debe llegar a un objeto liberado
    assert not window.get_visible() and window._closing and not window.is_destroyed()
    window.close()                                              # un segundo cierre no hace nada
    assert not window.is_destroyed()
    _pump(context, 8, window.is_destroyed)
    assert window.is_destroyed(), "la ventana debe destruirse cuando la CLI ha terminado"


def test_a_window_whose_cli_has_already_exited_is_destroyed_by_closing_it():
    window, context = _open(["true"])
    _pump(context, 5, lambda: not window._pid)                  # la CLI de prueba sale al instante
    assert not window._pid
    window.close()
    _pump(context, 1)
    assert window.is_destroyed() and not window._closing


def test_shutdown_ends_a_cli_that_ignores_hangup_and_terminate_without_waiting_for_the_event_loop():
    import os
    import time
    window, context = _open(["sh", "-c", "trap '' HUP TERM; exec sleep 61.9"])
    pid = window._pid
    assert pid
    started = time.monotonic()
    window.shutdown(wait=1.5)
    assert time.monotonic() - started < 2.5
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:                          # el hijo ya está muerto (a lo sumo, zombi hasta que el bucle lo recoja)
        context.iteration(False)
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
                if handle.read().rsplit(") ", 1)[-1].split()[0] == "Z":
                    break
        except FileNotFoundError:
            break
        time.sleep(0.02)
    else:
        raise AssertionError("la CLI sigue viva tras shutdown()")
    assert os.getsid(os.getpid()) != pid
    window.shutdown()                                           # sin CLI no hace nada
