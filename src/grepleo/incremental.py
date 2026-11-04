"""Búsquedas incrementales: repetir una búsqueda pidiendo solo lo publicado desde la última vez.

Los Actors cobran por oferta devuelta, así que pedir solo las novedades es el ahorro más directo. Sin GTK ni red.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import Job, JobState
from .sources.base import POSTED, SearchQuery
from .textutil import normalize

# Ventanas de fecha que entienden todas las fuentes, de la más corta a la más larga, con las horas máximas que
# cubren con margen. «Último mes» son 14 o 15 días en InfoJobs e Indeed: más allá no se garantiza la cobertura.
_WINDOWS = (("day", 22), ("week", 6 * 24), ("month", 13 * 24))
STALE_DAYS = 60   # una oferta publicada hace más de esto se retira de la lista, salvo las que tienen estado o seguimiento


def _rank(posted: str) -> int:
    """Cuanto más pequeño, más reciente la ventana; «sin filtro» es la más amplia."""
    return POSTED.index(posted) if posted in POSTED and posted else len(POSTED)


def incremental_posted(user_posted: str, ran_at: str, now: datetime) -> str | None:
    """La ventana de fechas que cubre desde la última búsqueda, o None si ya pasó demasiado para pedir solo novedades.

    Si la persona eligió ya una ventana más corta («Últimas 24 horas»), manda la suya.
    """
    try:
        last = datetime.fromisoformat(ran_at)
    except ValueError:
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    hours = max((now - last).total_seconds() / 3600, 0.0)
    window = next((name for name, limit in _WINDOWS if hours <= limit), None)
    if window is None:
        return None
    return window if _rank(window) <= _rank(user_posted) else user_posted


def same_search(first: SearchQuery, second: SearchQuery) -> bool:
    """Si dos consultas piden lo mismo (el número de ofertas y la fecha elegida no cuentan)."""
    def key(query: SearchQuery) -> tuple[str, str, bool]:
        return " ".join(normalize(query.keywords).split()), " ".join(normalize(query.location).split()), query.remote
    return key(first) == key(second)


def prune_stale(jobs: list[Job], now: datetime, days: int = STALE_DAYS) -> list[Job]:
    """Quita de las ofertas guardadas las antiguas. Una oferta sin fecha, favorita, postulada o con seguimiento (notas,
    recordatorio, fase, próximos pasos o histórico) se conserva."""
    cutoff = (now - timedelta(days=days)).date().isoformat()
    return [job for job in jobs
            if job.state in (JobState.FAVORITE, JobState.APPLIED) or job.has_tracking or job.posted[:10].count("-") != 2
            or job.posted[:10] >= cutoff]
