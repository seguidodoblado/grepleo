from pathlib import Path

from grepleo.models import Job, JobState, WorkMode
from grepleo.profiles import Profile
from grepleo.sources.base import SearchQuery
from grepleo.storage import DB_PATH, Store, job_from_dict, job_to_dict


def make_job(key="indeed:1", **changes):
    base = {"key": key, "source": "indeed", "title": "PO", "company": "ACME", "work_mode": WorkMode.HYBRID,
            "salary_min": 30000.0, "salary_max": 40000.0, "description": "texto", "full_description": True}
    base.update(changes)
    return Job(**base)


def test_the_database_lives_in_the_isolated_test_folder_not_in_the_real_home():
    assert "grepleo-tests-" in str(DB_PATH)


def test_a_job_round_trips_and_tolerates_bad_values():
    job = make_job(salary_estimated=True, closed=True)
    assert job_from_dict(job_to_dict(job)) == job
    odd = job_from_dict({"key": "k", "work_mode": "volando", "salary_min": "mucho", "title": 5}, "raro")
    assert odd.work_mode is WorkMode.UNKNOWN and odd.salary_min is None and odd.state is JobState.NEW
    assert odd.title == "5"


def test_profiles_are_saved_updated_listed_and_deleted():
    store = Store(Path(":memory:"))
    first = store.save_profile(Profile(name="Beta", years=3))
    store.save_profile(Profile(name="alfa"))
    assert [p.name for _id, p in store.list_profiles()] == ["alfa", "Beta"]
    store.save_profile(Profile(name="Beta", years=9), first)
    assert {i: p.years for i, p in store.list_profiles()}[first] == 9
    store.delete_profile(first)
    assert [p.name for _id, p in store.list_profiles()] == ["alfa"]


def test_a_broken_profile_does_not_break_the_list():
    store = Store(Path(":memory:"))
    store.save_profile(Profile(name="bien"))
    store._db.execute("INSERT INTO profiles (name, data) VALUES ('roto', '{no json')")
    assert [p.name for _id, p in store.list_profiles()] == ["bien"]


def test_searches_are_saved_and_listed_with_their_sources():
    store = Store(Path(":memory:"))
    profile_id = store.save_profile(Profile(name="PO"))
    query = SearchQuery("product owner", "Madrid", 40, "week", True)
    identifier = store.save_search("PO Madrid", profile_id, query, ["indeed", "linkedin"])
    saved = store.list_searches()[0]
    assert saved.id == identifier and saved.query == query and saved.sources == ["indeed", "linkedin"]
    assert saved.profile_id == profile_id and saved.ran_at == ""
    store.save_search("PO Madrid", None, SearchQuery("po"), ["indeed"], identifier)
    assert store.list_searches()[0].profile_id is None and store.list_searches()[0].query.keywords == "po"
    store.delete_profile(profile_id)
    store.delete_search(identifier)
    assert store.list_searches() == []


def test_results_keep_the_state_of_jobs_seen_before():
    store = Store(Path(":memory:"))
    search = store.save_search("s", None, SearchQuery("po"), ["indeed"])
    store.store_results(search, [make_job("indeed:1"), make_job("indeed:2")])
    store.set_state("indeed:1", JobState.DISCARDED)
    store.set_state("indeed:2", JobState.FAVORITE)
    store.store_results(search, [make_job("indeed:1", title="PO (actualizada)"), make_job("indeed:3")])
    jobs = {job.key: job for job in store.jobs_for_search(search)}
    assert set(jobs) == {"indeed:1", "indeed:3"}               # los resultados anteriores se sustituyen
    assert jobs["indeed:1"].state is JobState.DISCARDED and jobs["indeed:1"].title == "PO (actualizada)"
    assert jobs["indeed:3"].state is JobState.NEW
    assert store.list_searches()[0].ran_at != ""


def test_a_job_shared_by_two_searches_has_one_state():
    store = Store(Path(":memory:"))
    one = store.save_search("a", None, SearchQuery("x"), ["indeed"])
    two = store.save_search("b", None, SearchQuery("y"), ["indeed"])
    store.store_results(one, [make_job()])
    store.store_results(two, [make_job()])
    store.set_state("indeed:1", JobState.APPLIED)
    assert store.jobs_for_search(two)[0].state is JobState.APPLIED
