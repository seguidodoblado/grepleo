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
