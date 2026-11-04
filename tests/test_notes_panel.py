import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from grepleo.models import Job
from grepleo.ui.notes_panel import NotesPanel


def read(panel):
    buffer = panel.text.get_buffer()
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)


def test_typing_is_saved_when_flushed_and_when_another_offer_is_chosen():
    saved = []
    panel = NotesPanel(lambda job, notes: saved.append((job.key, notes)))
    first, second = Job(key="a", source="x", title="A"), Job(key="b", source="x", title="B", notes="ya había algo")
    assert not panel.text.get_sensitive()          # sin oferta elegida no se escribe
    panel.load(first)
    panel.text.get_buffer().set_text("  Entrevista el martes, ofrecen 45k  ", -1)
    assert saved == []                              # se guarda con retraso, no en cada tecla
    panel.load(second)                              # al cambiar de oferta se guarda lo pendiente en la anterior
    assert saved == [("a", "Entrevista el martes, ofrecen 45k")]
    assert read(panel) == "ya había algo"
    panel.load(None)
    assert not panel.text.get_sensitive() and read(panel) == ""
