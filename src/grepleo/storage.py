"""Base de datos local (SQLite): perfiles, búsquedas guardadas, ofertas vistas y su estado.

Todo vive en ~/.local/share/grepleo/grepleo.db y se usa solo desde el hilo principal.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import EventKind, Job, JobEvent, JobState, WorkMode
from .profiles import Profile
from .sources.base import SearchQuery

DATA_DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "grepleo"
DB_PATH = DATA_DIR / "grepleo.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, profile_id INTEGER,
    keywords TEXT NOT NULL, location TEXT NOT NULL, limit_n INTEGER NOT NULL, posted TEXT NOT NULL,
    remote INTEGER NOT NULL, sources TEXT NOT NULL, ran_at TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    key TEXT PRIMARY KEY, data TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'new', first_seen TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '', remind_on TEXT NOT NULL DEFAULT '', stage TEXT NOT NULL DEFAULT '',
    next_steps TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS results (
    search_id INTEGER NOT NULL, job_key TEXT NOT NULL, PRIMARY KEY (search_id, job_key));
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, job_key TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_by_job ON events (job_key);
CREATE TABLE IF NOT EXISTS geocache (
    place TEXT PRIMARY KEY, lat REAL, lon REAL, found INTEGER NOT NULL, at TEXT NOT NULL);
"""


@dataclass
class SavedSearch:
    id: int
    name: str
    profile_id: int | None
    query: SearchQuery
    sources: list[str]
    ran_at: str = ""


def job_to_dict(job: Job) -> dict[str, Any]:
    return {
        "key": job.key, "source": job.source, "title": job.title, "company": job.company,
        "location": job.location, "work_mode": job.work_mode.value, "contract": job.contract,
        "salary_min": job.salary_min, "salary_max": job.salary_max, "salary_text": job.salary_text,
        "salary_estimated": job.salary_estimated, "experience_text": job.experience_text,
        "studies_text": job.studies_text, "description": job.description,
        "full_description": job.full_description, "url": job.url, "posted": job.posted, "closed": job.closed,
    }


def job_from_dict(data: dict[str, Any], state: str = "new", notes: str = "", remind_on: str = "", stage: str = "",
                  next_steps: str = "", event_count: int = 0) -> Job:
    try:
        mode = WorkMode(data.get("work_mode", "unknown"))
    except ValueError:
        mode = WorkMode.UNKNOWN
    try:
        job_state = JobState(state)
    except ValueError:
        job_state = JobState.NEW

    def number(key: str) -> float | None:
        value = data.get(key)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    return Job(
        key=str(data.get("key", "")), source=str(data.get("source", "")), title=str(data.get("title", "")),
        company=str(data.get("company", "")), location=str(data.get("location", "")), work_mode=mode,
        contract=str(data.get("contract", "")), salary_min=number("salary_min"), salary_max=number("salary_max"),
        salary_text=str(data.get("salary_text", "")), salary_estimated=bool(data.get("salary_estimated")),
        experience_text=str(data.get("experience_text", "")), studies_text=str(data.get("studies_text", "")),
        description=str(data.get("description", "")), full_description=bool(data.get("full_description")),
        url=str(data.get("url", "")), posted=str(data.get("posted", "")), closed=bool(data.get("closed")),
        state=job_state, notes=notes or "", remind_on=remind_on or "",
        stage=stage or "", next_steps=next_steps or "", event_count=event_count or 0,
    )


class Store:
    def __init__(self, path: Path = DB_PATH) -> None:
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.executescript(_SCHEMA)
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(jobs)")}
        for column in ("notes", "remind_on", "stage", "next_steps"):   # bases de datos creadas antes de las notas
            if column not in columns:
                self._db.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        self._db.commit()
        self._migrate_skill_levels(path)

    def _migrate_skill_levels(self, path: Path) -> None:
        """Los perfiles guardados antes de que cada habilidad tuviera su nivel se reescriben con él (ver
        `profiles._skill_levels`), después de dejar una copia de seguridad de la base de datos: `grepleo.db.antes-de-niveles`
        (una sola vez; si ya existe, no se toca)."""
        old = []
        for identifier, data in self._db.execute("SELECT id, data FROM profiles").fetchall():
            try:
                parsed = json.loads(data)
            except ValueError:
                continue
            if isinstance(parsed, dict) and "skill_levels" not in parsed:
                old.append((identifier, parsed))
        if not old:
            return
        if str(path) != ":memory:":
            backup = path.with_name(path.name + ".antes-de-niveles")
            if not backup.exists():
                copy = sqlite3.connect(str(backup))
                try:
                    self._db.backup(copy)
                finally:
                    copy.close()
        with self._db:
            for identifier, parsed in old:
                data = json.dumps(Profile.from_dict(parsed).to_dict(), ensure_ascii=False)
                self._db.execute("UPDATE profiles SET data = ? WHERE id = ?", (data, identifier))

    def close(self) -> None:
        self._db.close()

    # --- lugares del mapa -------------------------------------------------------------------------
    def cached_places(self, places: list[str]) -> dict[str, tuple[float, float] | None]:
        """Lo que ya se sabe de estos lugares: su punto, o None si se preguntó y no existe. Los que no se han preguntado
        nunca no salen."""
        known: dict[str, tuple[float, float] | None] = {}
        for place in places:
            row = self._db.execute("SELECT lat, lon, found FROM geocache WHERE place = ?", (place.casefold(),)).fetchone()
            if row is not None:
                known[place] = (row[0], row[1]) if row[2] else None
        return known

    def save_place(self, place: str, coordinates: tuple[float, float] | None) -> None:
        with self._db:
            self._db.execute("INSERT OR REPLACE INTO geocache (place, lat, lon, found, at) VALUES (?, ?, ?, ?, ?)",
                             (place.casefold(), coordinates[0] if coordinates else None,
                              coordinates[1] if coordinates else None, 1 if coordinates else 0,
                              datetime.now(timezone.utc).isoformat()))

    # --- perfiles ---------------------------------------------------------------------------------
    def list_profiles(self) -> list[tuple[int, Profile]]:
        rows = self._db.execute("SELECT id, data FROM profiles ORDER BY name COLLATE NOCASE").fetchall()
        profiles = []
        for identifier, data in rows:
            try:
                profiles.append((identifier, Profile.from_dict(json.loads(data))))
            except ValueError:
                continue   # un perfil con el JSON roto no tumba la lista
        return profiles

    def save_profile(self, profile: Profile, identifier: int | None = None) -> int:
        data = json.dumps(profile.to_dict(), ensure_ascii=False)
        with self._db:
            if identifier is None:
                cursor = self._db.execute("INSERT INTO profiles (name, data) VALUES (?, ?)", (profile.name, data))
                return int(cursor.lastrowid or 0)
            self._db.execute("UPDATE profiles SET name = ?, data = ? WHERE id = ?", (profile.name, data, identifier))
            return identifier

    def delete_profile(self, identifier: int) -> None:
        with self._db:
            self._db.execute("DELETE FROM profiles WHERE id = ?", (identifier,))
            self._db.execute("UPDATE searches SET profile_id = NULL WHERE profile_id = ?", (identifier,))

    # --- búsquedas guardadas ----------------------------------------------------------------------
    def save_search(self, name: str, profile_id: int | None, query: SearchQuery, sources: list[str],
                    identifier: int | None = None) -> int:
        values = (name, profile_id, query.keywords, query.location, query.limit, query.posted,
                  int(query.remote), json.dumps(sources))
        with self._db:
            if identifier is None:
                cursor = self._db.execute(
                    "INSERT INTO searches (name, profile_id, keywords, location, limit_n, posted, remote, sources)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
                return int(cursor.lastrowid or 0)
            self._db.execute(
                "UPDATE searches SET name = ?, profile_id = ?, keywords = ?, location = ?, limit_n = ?, posted = ?,"
                " remote = ?, sources = ? WHERE id = ?", (*values, identifier))
            return identifier

    def list_searches(self) -> list[SavedSearch]:
        rows = self._db.execute(
            "SELECT id, name, profile_id, keywords, location, limit_n, posted, remote, sources, ran_at"
            " FROM searches ORDER BY name COLLATE NOCASE").fetchall()
        searches = []
        for identifier, name, profile_id, keywords, location, limit, posted, remote, sources, ran_at in rows:
            try:
                source_ids = [str(item) for item in json.loads(sources)]
            except ValueError:
                source_ids = []
            searches.append(SavedSearch(identifier, name, profile_id,
                                        SearchQuery(keywords, location, limit, posted, bool(remote)),
                                        source_ids, ran_at or ""))
        return searches

    def delete_search(self, identifier: int) -> None:
        with self._db:
            self._db.execute("DELETE FROM results WHERE search_id = ?", (identifier,))
            self._db.execute("DELETE FROM searches WHERE id = ?", (identifier,))

    # --- ofertas ----------------------------------------------------------------------------------
    def store_results(self, search_id: int, jobs: list[Job]) -> None:
        """Guarda las ofertas de una búsqueda (sustituyendo las anteriores de esa búsqueda). Las ya conocidas
        conservan su estado: una oferta descartada no vuelve a aparecer como nueva."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._db:
            self._db.execute("DELETE FROM results WHERE search_id = ?", (search_id,))
            for job in jobs:
                data = json.dumps(job_to_dict(job), ensure_ascii=False)
                self._db.execute(
                    "INSERT INTO jobs (key, data, state, first_seen) VALUES (?, ?, 'new', ?)"
                    " ON CONFLICT(key) DO UPDATE SET data = excluded.data", (job.key, data, now))
                self._db.execute("INSERT OR IGNORE INTO results (search_id, job_key) VALUES (?, ?)",
                                 (search_id, job.key))
            self._db.execute("UPDATE searches SET ran_at = ? WHERE id = ?", (now, search_id))

    def jobs_for_search(self, search_id: int) -> list[Job]:
        rows = self._db.execute(
            "SELECT jobs.data, jobs.state, jobs.notes, jobs.remind_on, jobs.stage, jobs.next_steps,"
            " (SELECT COUNT(*) FROM events WHERE events.job_key = jobs.key)"
            " FROM results JOIN jobs ON jobs.key = results.job_key"
            " WHERE results.search_id = ? ORDER BY jobs.first_seen DESC, jobs.key", (search_id,)).fetchall()
        jobs = []
        for data, state, notes, remind_on, stage, next_steps, event_count in rows:
            try:
                jobs.append(job_from_dict(json.loads(data), state, notes, remind_on, stage, next_steps, event_count))
            except ValueError:
                continue
        return jobs

    def set_notes(self, job_key: str, notes: str, remind_on: str | None = None) -> None:
        """Guarda las notas de una oferta (y, si se da, la fecha del recordatorio). Viven aparte de los datos de la
        oferta: una nueva búsqueda que vuelva a traerla no las toca."""
        with self._db:
            if remind_on is None:
                self._db.execute("UPDATE jobs SET notes = ? WHERE key = ?", (notes, job_key))
            else:
                self._db.execute("UPDATE jobs SET notes = ?, remind_on = ? WHERE key = ?",
                                 (notes, remind_on, job_key))

    def set_tracking(self, job_key: str, stage: str, next_steps: str, remind_on: str) -> None:
        """Guarda la fase del proceso, los próximos pasos y el recordatorio de una oferta."""
        with self._db:
            self._db.execute("UPDATE jobs SET stage = ?, next_steps = ?, remind_on = ? WHERE key = ?",
                             (stage, next_steps, remind_on, job_key))

    # --- histórico de una oferta -------------------------------------------------------------------
    def list_events(self, job_key: str) -> list[JobEvent]:
        """El histórico de una oferta, de lo más reciente a lo más antiguo."""
        rows = self._db.execute("SELECT id, day, kind, text FROM events WHERE job_key = ? ORDER BY day DESC, id DESC",
                                (job_key,)).fetchall()
        events = []
        for identifier, day, kind, text in rows:
            try:
                events.append(JobEvent(identifier, day, EventKind(kind), text))
            except ValueError:
                events.append(JobEvent(identifier, day, EventKind.OTHER, text))
        return events

    def add_event(self, job_key: str, day: str, kind: EventKind, text: str) -> int:
        with self._db:
            cursor = self._db.execute("INSERT INTO events (job_key, day, kind, text) VALUES (?, ?, ?, ?)",
                                      (job_key, day, kind.value, text))
        return int(cursor.lastrowid or 0)

    def update_event(self, identifier: int, day: str, kind: EventKind, text: str) -> None:
        with self._db:
            self._db.execute("UPDATE events SET day = ?, kind = ?, text = ? WHERE id = ?",
                             (day, kind.value, text, identifier))

    def delete_event(self, identifier: int) -> None:
        with self._db:
            self._db.execute("DELETE FROM events WHERE id = ?", (identifier,))

    def due_reminders(self, today: str) -> list[tuple[str, str, str]]:
        """Los recordatorios que vencen hoy o antes, de cualquier búsqueda: (clave, título, fecha), los más viejos primero."""
        rows = self._db.execute(
            "SELECT key, data, remind_on FROM jobs WHERE remind_on != '' AND remind_on <= ? ORDER BY remind_on, key",
            (today,)).fetchall()
        due = []
        for key, data, remind_on in rows:
            try:
                title = str(json.loads(data).get("title", ""))
            except ValueError:
                title = ""
            due.append((key, title, remind_on))
        return due

    def set_state(self, job_key: str, state: JobState) -> None:
        with self._db:
            self._db.execute("UPDATE jobs SET state = ? WHERE key = ?", (state.value, job_key))
