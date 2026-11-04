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


def test_block_parent_disables_the_parent_while_the_window_is_shown_and_restores_it_on_close_or_destroy():
    from gi.repository import GLib, Gtk

    from grepleo.ui.common import block_parent
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets")

    def pump():
        context = GLib.MainContext.default()
        while context.iteration(False):
            pass
    for how in ("close", "destroy"):
        parent, window = Gtk.Window(), Gtk.Window()
        block_parent(window, parent)
        assert parent.get_sensitive()                       # aún no se ha mostrado: no bloquea
        window.present()
        pump()
        assert not parent.get_sensitive() and window.get_transient_for() is None and not window.get_modal()
        (window.close if how == "close" else window.destroy)()
        pump()
        assert parent.get_sensitive()
    block_parent(Gtk.Window(), None)                        # sin ventana madre no hace nada


def test_the_main_window_keeps_a_small_minimum_size_so_it_can_be_maximized_on_a_1080p_screen():
    """Con una tipografía grande, el mínimo de la ventana superó el alto útil de una pantalla de 1080 px y el gestor de
    ventanas ya no la dejaba maximizar (al desmarcar «Solo novedades» el ancho mínimo bajaba y la altura mínima sin ancho
    fijado subía): el panel lateral debe poder encogerse y el texto del coste, acortarse con puntos suspensivos."""
    from pathlib import Path

    from gi.repository import Gtk, Pango

    from grepleo.profiles import Profile
    from grepleo.sources.base import SearchQuery
    from grepleo.storage import Store
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets")
    settings = Gtk.Settings.get_default()
    previous = settings.get_property("gtk-font-name")
    settings.set_property("gtk-font-name", "Sans 17")       # más grande que la de un escritorio normal
    try:
        store = Store(Path(":memory:"))
        profile_id = store.save_profile(Profile(name="P", must=["AWS"]))
        search = store.save_search(gui.LAST_SEARCH, profile_id, SearchQuery("devops"), ["indeed"])
        store.store_results(search, [Job(key="x:1", source="indeed", title="Oferta", description="AWS " * 40,
                                         full_description=True)])
        window = gui.MainWindow(Gtk.Application(application_id="io.github.seguidodoblado.GrepleoMinSize"), store)
        assert window.estimate.get_ellipsize() is Pango.EllipsizeMode.END
        for incremental in (True, False):
            window.incremental.set_active(incremental)
            minimum_width = window.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
            minimum_height = window.measure(Gtk.Orientation.VERTICAL, -1)[0]
            assert minimum_width <= 1700, f"ancho mínimo {minimum_width} con incremental={incremental}"
            assert minimum_height <= 1000, f"alto mínimo {minimum_height} con incremental={incremental}"
    finally:
        settings.set_property("gtk-font-name", previous)


def test_the_ats_column_is_filled_in_the_background_and_can_be_filtered_and_sorted():
    from pathlib import Path

    from gi.repository import GLib, Gtk

    from grepleo.profiles import Profile
    from grepleo.sources.base import SearchQuery
    from grepleo.storage import Store
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets")
    rich = "Requisitos:\n- AWS y Docker\n- Terraform\n" * 6
    poor = "Requisitos:\n- Cobol y Fortran\n- Mainframe y JCL\n" * 6
    store = Store(Path(":memory:"))
    profile_id = store.save_profile(Profile(name="P", headline="DevOps", years=3, must=["AWS", "Docker", "Terraform"],
                                            experience="DevOps con AWS y Docker"))
    search = store.save_search(gui.LAST_SEARCH, profile_id, SearchQuery("devops"), ["indeed"])
    store.store_results(search, [Job(key="x:good", source="indeed", title="DevOps AWS", description=rich,
                                     full_description=True),
                                 Job(key="x:bad", source="indeed", title="Programador Cobol", description=poor,
                                     full_description=True)])
    window = gui.MainWindow(Gtk.Application(application_id="io.github.seguidodoblado.GrepleoAts"), store)
    items = [window.store_model.get_item(i) for i in range(window.store_model.get_n_items())]
    pending = [item for item in items if item.ats_percent < 0]          # la oferta elegida se calcula al momento; el resto, después
    assert pending, "la ventana no debe calcular todo antes de mostrarse"
    assert gui.ats_text(pending[0]) == "…" and "Calculando" in gui.ats_tooltip(pending[0])
    context = GLib.MainContext.default()
    for _attempt in range(50):                                          # las tandas llegan cuando el bucle está libre
        while context.iteration(False):
            pass
        if all(item.ats_percent >= 0 for item in items):
            break
    percents = {item.job.key: item.ats_percent for item in items}
    assert all(0 <= value <= 100 for value in percents.values()) and percents["x:good"] > percents["x:bad"]
    good = next(item for item in items if item.job.key == "x:good")
    assert gui.ats_text(good) == f"{percents['x:good']} %" and good.ats.verdict in gui.ats_tooltip(good)
    labels = gui.ats_filter_labels()
    assert len(labels) == len(gui.ATS_FILTERS) and labels[0].startswith("ATS")
    window.filter_ats.set_selected(1)                                   # probable: ≥ 70 %
    assert window.filter_model.get_n_items() == (1 if percents["x:good"] >= 70 else 0)
    window.filter_ats.set_selected(3)                                   # poco probable: < 45 %
    assert {window.filter_model.get_item(i).job.key for i in range(window.filter_model.get_n_items())} >= (
        {"x:bad"} if percents["x:bad"] < 45 else set())
    window.filter_ats.set_selected(0)
    assert window.filter_model.get_n_items() == 2
    by_ats = gui.MainWindow._sorter_for("ats")
    assert by_ats(good, next(item for item in items if item is not good)) > 0       # el mejor va por delante al ordenar
    # al cambiar el perfil, las estimaciones guardadas dejan de valer
    key_before = window._ats_profile_key
    window._queue_ats(items, Profile(name="Otro", years=0))
    assert window._ats_profile_key != key_before


def test_fit_column_shows_the_weighted_score_that_sorts_and_the_count_in_the_tooltip():
    from grepleo.ui.gui import fit_text, fit_tooltip

    class Item:
        evaluation = Evaluation(Fit.MEDIUM, 0.624, [CriterionResult("a", Status.MET, "", 1.0),
                                                   CriterionResult("b", Status.MISSING, "", 1.0)])
    assert fit_text(Item).endswith("62 %") and "1/2" in fit_tooltip(Item)
    Item.evaluation = Evaluation(Fit.UNKNOWN, None)
    assert "%" not in fit_text(Item)


def test_the_panorama_fills_in_the_gaps_section_in_the_background():
    from pathlib import Path

    from gi.repository import GLib, Gtk

    from grepleo.profiles import Profile
    from grepleo.sources.base import SearchQuery
    from grepleo.storage import Store
    from grepleo.ui import gui
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets")
    text = "Requisitos:\n- Jenkins y Docker\n" * 6
    store = Store(Path(":memory:"))
    profile_id = store.save_profile(Profile(name="P", headline="DevOps", must=["Docker"]))
    search = store.save_search(gui.LAST_SEARCH, profile_id, SearchQuery("devops"), ["indeed"])
    store.store_results(search, [Job(key="x:1", source="indeed", title="DevOps", description=text,
                                     full_description=True)])
    window = gui.MainWindow(Gtk.Application(application_id="io.github.seguidodoblado.GrepleoGaps"), store)
    context = GLib.MainContext.default()
    shown = ""
    for _attempt in range(200):
        while context.iteration(False):
            pass
        shown = _all_labels(window.panorama_box)
        if "Jenkins" in shown and "Docker" in shown and "Calculando" not in shown:
            break
        GLib.usleep(10000)
    assert "Qué te falta más veces" in shown and "Tus puntos fuertes" in shown and "Jenkins" in shown
    assert "Docker" in shown and "Calculando" not in shown


def _all_labels(widget) -> str:
    """El texto de todas las etiquetas bajo un widget."""
    parts, child = [], widget.get_first_child()
    while child is not None:
        if hasattr(child, "get_text") and not hasattr(child, "get_buffer") and hasattr(child, "get_label"):
            parts.append(child.get_label() or "")
        parts.append(_all_labels(child))
        child = child.get_next_sibling()
    return "\n".join(parts)
