import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from datetime import date
from pathlib import Path

from grepleo.models import EventKind, Job, Stage
from grepleo.sources.base import SearchQuery
from grepleo.storage import Store
from grepleo.ui.tracking_panel import TrackingPanel


def make_panel(*keys):
    """Un panel sobre una base de datos real en memoria, con las ofertas dadas ya guardadas."""
    store = Store(Path(":memory:"))
    search = store.save_search("s", None, SearchQuery("po"), [])
    store.store_results(search, [Job(key=key, source="x", title=key) for key in keys])
    changed = []
    return store, TrackingPanel(store, changed.append), changed, {job.key: job for job in store.jobs_for_search(search)}


def stored(store, key):
    row = store._db.execute("SELECT stage, next_steps, remind_on FROM jobs WHERE key = ?", (key,)).fetchone()
    return row


def rows(panel):
    count, row = 0, panel.events.get_first_child()
    while row is not None:
        count, row = count + 1, row.get_next_sibling()
    return count


def test_the_stage_and_reminder_are_saved_and_reported():
    store, panel, changed, jobs = make_panel("x:1")
    job = jobs["x:1"]
    panel.load(job)
    assert panel.empty.get_visible() and not panel.events.get_visible()      # «Aún no hay nada apuntado»
    panel.stage.set_selected(list(Stage).index(Stage.FINAL))
    assert job.stage == "final" and changed[-1] is job
    panel.reminder.choose(date(2026, 11, 20))
    assert job.remind_on == "2026-11-20"
    assert stored(store, "x:1") == ("final", "", "2026-11-20")


def test_next_steps_are_saved_when_flushed_or_when_another_offer_is_chosen():
    store, panel, changed, jobs = make_panel("a", "b")
    first, second = jobs["a"], jobs["b"]
    second.stage = "suspended"
    panel.load(first)
    panel.steps.get_buffer().set_text("  Esperar la llamada del viernes  ", -1)
    assert first.next_steps == ""                      # con retraso
    panel.load(second)
    assert first.next_steps == "Esperar la llamada del viernes" and changed[-1] is first
    assert stored(store, "a")[1] == "Esperar la llamada del viernes"
    assert list(Stage)[panel.stage.get_selected()] is Stage.SUSPENDED     # el seguimiento de la otra oferta


def test_events_are_added_edited_and_deleted_in_the_history():
    store, panel, changed, jobs = make_panel("x:1")
    job = jobs["x:1"]
    panel.load(job)
    panel.day.set_day("2026-11-05")
    panel.kind.set_selected(list(EventKind).index(EventKind.INTERVIEW))
    panel.text.set_text("Entrevista con Luis, piden Kubernetes")
    panel.submit_button.emit("clicked")
    assert rows(panel) == 1 and job.event_count == 1 and changed[-1] is job
    event = store.list_events("x:1")[0]
    assert (event.day, event.kind, event.text) == ("2026-11-05", EventKind.INTERVIEW, "Entrevista con Luis, piden Kubernetes")
    assert panel.text.get_text() == ""                 # el formulario queda listo para otra anotación
    panel._start_editing(event)
    assert panel.submit_button.get_label() != "" and panel.cancel_button.get_visible()
    panel.text.set_text("Entrevista con Luis (segunda)")
    panel._submit()
    assert store.list_events("x:1")[0].text == "Entrevista con Luis (segunda)" and rows(panel) == 1
    panel._delete(store.list_events("x:1")[0])
    assert rows(panel) == 0 and job.event_count == 0 and panel.empty.get_visible()


def test_without_an_offer_nothing_can_be_edited():
    _store, panel, changed, _jobs = make_panel()
    panel.load(None)
    assert not panel.stage.get_sensitive() and not panel.submit_button.get_sensitive()
    panel._submit()
    assert changed == []
