from datetime import datetime, timedelta, timezone

from grepleo.incremental import incremental_posted, prune_stale, same_search
from grepleo.models import Job, JobState
from grepleo.sources import SearchQuery

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def ago(**delta) -> str:
    return (NOW - timedelta(**delta)).isoformat(timespec="seconds")


def test_the_window_is_the_shortest_one_that_covers_the_gap():
    assert incremental_posted("", ago(hours=3), NOW) == "day"
    assert incremental_posted("", ago(hours=23), NOW) == "week"     # 24 h justas no dejan margen
    assert incremental_posted("", ago(days=3), NOW) == "week"
    assert incremental_posted("", ago(days=9), NOW) == "month"
    assert incremental_posted("", ago(days=20), NOW) is None        # ya no se puede garantizar: búsqueda completa
    assert incremental_posted("", "no es una fecha", NOW) is None
    assert incremental_posted("", ago(hours=-5), NOW) == "day"      # un reloj adelantado no rompe nada


def test_a_shorter_window_chosen_by_the_user_wins():
    assert incremental_posted("day", ago(days=3), NOW) == "day"
    assert incremental_posted("month", ago(days=3), NOW) == "week"
    assert incremental_posted("week", ago(days=3), NOW) == "week"
    assert incremental_posted("", ago(hours=3).replace("+00:00", ""), NOW) == "day"   # sin zona: se toma UTC


def test_same_search_ignores_limit_date_case_and_accents():
    base = SearchQuery("Product Owner", "Madrid", 50, "week", False)
    assert same_search(base, SearchQuery("  product   owner ", "madrid", 100, "", False))
    assert same_search(SearchQuery("Gestión", "", 10), SearchQuery("gestion", "", 20))
    assert not same_search(base, SearchQuery("Product Owner", "Madrid", 50, "week", True))
    assert not same_search(base, SearchQuery("Product Owner", "Barcelona", 50, "week", False))
    assert not same_search(base, SearchQuery("Scrum Master", "Madrid", 50, "week", False))


def test_prune_drops_old_offers_but_keeps_the_ones_that_matter():
    def job(key, posted, state=JobState.NEW):
        return Job(key=key, source="x", title="t", posted=posted, state=state)

    jobs = [job("a", "2026-11-01"), job("b", "2026-08-01"), job("c", "2026-08-01", JobState.FAVORITE),
            job("d", "2026-08-01", JobState.APPLIED), job("e", ""), job("f", "ayer"), job("g", "2026-09-05")]
    assert [j.key for j in prune_stale(jobs, NOW)] == ["a", "c", "d", "e", "f", "g"]


def test_prune_keeps_old_offers_that_have_notes_or_a_reminder():
    from datetime import datetime, timezone

    from grepleo.incremental import prune_stale
    from grepleo.models import Job
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    old = {"posted": "2026-01-01"}
    jobs = [Job(key="a", source="x", title="a", **old), Job(key="b", source="x", title="b", notes="entrevista", **old),
            Job(key="c", source="x", title="c", remind_on="2026-11-10", **old),
            Job(key="d", source="x", title="d", stage="final", **old), Job(key="e", source="x", title="e", event_count=2, **old),
            Job(key="f", source="x", title="f", **old)]
    assert [job.key for job in prune_stale(jobs, now)] == ["b", "c", "d", "e"]
