import pytest

pytest.importorskip("gi")
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from grepleo.ui import gui
except (ImportError, ValueError):   # sin GTK 4 no hay interfaz que probar
    pytest.skip("GTK 4 no está disponible", allow_module_level=True)

from grepleo.models import CriterionResult, Evaluation, Fit, Job, Status


def job(source, title="Product Owner", company="ACME", location="Madrid", full=False):
    return Job(key=f"{source}:1", source=source, title=title, company=company, location=location,
               full_description=full)


def test_the_same_job_from_two_sources_is_kept_once_preferring_the_full_description():
    summary = job("infojobs")
    full = job("indeed", title="PRODUCTO owner", full=False)   # otro título: otra oferta
    same_but_full = job("linkedin", title="product owner", company="acme", location="MADRID", full=True)
    merged = gui.merge_jobs([summary, full, same_but_full])
    assert len(merged) == 2
    assert {j.source for j in merged} == {"linkedin", "indeed"}
    assert gui.duplicate_key(summary) == gui.duplicate_key(same_but_full)
    assert gui.merge_jobs([]) == []


def test_the_criteria_column_and_the_salary_column_texts():
    evaluation = Evaluation(Fit.HIGH, 0.8, [CriterionResult("Scrum", Status.MET),
                                            CriterionResult("SQL", Status.MISSING),
                                            CriterionResult("Jira", Status.UNKNOWN)])
    assert gui.criteria_text(evaluation) == "✓ Scrum  ✗ SQL  ? Jira"
    assert gui.salary_text(Job(key="k", source="s", title="t")) == "—"
    estimated = Job(key="k", source="s", title="t", salary_text="40.000 €", salary_estimated=True)
    assert gui.salary_text(estimated) == "40.000 € (est.)"


def test_filter_label_lists_match_their_value_lists():
    assert len(gui.fit_filter_labels()) == len(gui.FIT_FILTERS)
    assert len(gui.state_filter_labels()) == len(gui.STATE_FILTERS)
    assert len(gui.posted_labels()) == 4


def test_notes_marks_and_tooltip():
    plain = job("indeed")
    assert gui.notes_mark(plain, "2026-11-10") == ""
    noted = Job(key="x:1", source="x", title="t", notes="Llamó Ana\nsegunda línea", remind_on="2026-11-20")
    assert gui.notes_mark(noted, "2026-11-10") == "notes"            # recordatorio futuro: solo un icono de notas
    assert gui.notes_mark(noted, "2026-11-20") == "due" and gui.notes_mark(noted, "2026-12-01") == "due"
    only_date = Job(key="x:2", source="x", title="t", remind_on="2026-11-05")
    assert gui.notes_mark(only_date, "2026-11-04") == "notes"
    assert gui.notes_tooltip(noted) == "Llamó Ana\nRecordatorio: 2026-11-20"
    assert len(gui.state_filter_labels()) == len(gui.STATE_FILTERS)


def test_state_text_adds_the_process_stage_and_the_tracking_marks_cover_every_kind_of_note():
    from grepleo.models import JobState
    plain = Job(key="x:1", source="x", title="t")
    assert gui.state_text(plain) == JobState.NEW.label
    final = Job(key="x:2", source="x", title="t", stage="final", state=JobState.APPLIED)
    assert gui.state_text(final) == f"{JobState.APPLIED.label}\nFase final"
    assert gui.state_text(Job(key="x:3", source="x", title="t", stage="invent")) == JobState.NEW.label   # clave rara
    assert gui.stage_of(final).is_open and not gui.stage_of(Job(key="y", source="x", title="t", stage="rejected")).is_open
    for changes in ({"next_steps": "Llamar"}, {"stage": "offer"}, {"event_count": 2}):
        assert gui.notes_mark(Job(key="z", source="x", title="t", **changes), "2026-11-10") == "notes"
    lines = gui.notes_tooltip(Job(key="z", source="x", title="t", stage="final", next_steps="Esperar a RRHH\nluego",
                                  event_count=2, remind_on="2026-11-20"))
    assert "Fase: Fase final" in lines and "Próximos pasos: Esperar a RRHH" in lines
    assert "2 anotaciones en el histórico" in lines and "Recordatorio: 2026-11-20" in lines


def test_mode_filter_labels_match_the_modes_and_say_that_unknown_ones_are_separate():
    from grepleo.models import WorkMode
    labels = gui.mode_filter_labels()
    assert len(labels) == len(gui.MODE_FILTERS)
    assert labels[1:4] == ["Remoto", "Híbrido", "Presencial"] and labels[0].startswith("Modalidad")
    assert gui.MODE_FILTERS == (None, WorkMode.REMOTE, WorkMode.HYBRID, WorkMode.ONSITE, WorkMode.UNKNOWN)


def test_the_mode_filter_keeps_only_the_offers_of_that_work_mode():
    from pathlib import Path

    from gi.repository import Gtk

    from grepleo.models import WorkMode
    from grepleo.profiles import Profile
    from grepleo.sources.base import SearchQuery
    from grepleo.storage import Store
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets")
    store = Store(Path(":memory:"))
    profile_id = store.save_profile(Profile(name="P", must=["AWS"]))
    search = store.save_search(gui.LAST_SEARCH, profile_id, SearchQuery("devops"), ["indeed"])
    modes = (WorkMode.REMOTE, WorkMode.HYBRID, WorkMode.HYBRID, WorkMode.ONSITE, WorkMode.UNKNOWN)
    store.store_results(search, [Job(key=f"x:{n}", source="indeed", title=f"Oferta {n}", work_mode=mode,
                                     description="AWS " * 40, full_description=True)
                                 for n, mode in enumerate(modes)])
    window = gui.MainWindow(Gtk.Application(application_id="io.github.seguidodoblado.GrepleoTest"), store)
    shown = {}
    for position, mode in enumerate(gui.MODE_FILTERS):
        window.filter_mode.set_selected(position)
        shown[mode] = window.filter_model.get_n_items()
    assert shown == {None: 5, WorkMode.REMOTE: 1, WorkMode.HYBRID: 2, WorkMode.ONSITE: 1, WorkMode.UNKNOWN: 1}
    window.filter_mode.set_selected(2)                       # los filtros se combinan con los demás
    window.filter_text.set_text("Oferta 2")
    window._filters_changed()                                 # la caja de búsqueda avisa con retraso: se fuerza
    assert window.filter_model.get_n_items() == 1
