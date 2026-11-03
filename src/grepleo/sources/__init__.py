"""Las fuentes de ofertas y la forma de lanzar una búsqueda en varias a la vez."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..models import Job
from .apify import ApifyError, run_actor
from .base import POSTED, SearchQuery, Source
from .indeed import Indeed
from .infojobs import InfoJobs
from .linkedin import LinkedIn

SOURCES: dict[str, Source] = {source.id: source for source in (InfoJobs(), Indeed(), LinkedIn())}

__all__ = ["POSTED", "SOURCES", "ApifyError", "SearchQuery", "Source", "SourceResult", "plan_search",
           "run_search"]


@dataclass
class PlannedRun:
    source: Source
    limit: int
    cap_usd: float          # tope de gasto que se le pasa a Apify
    estimate_usd: float


@dataclass
class SourceResult:
    source: Source
    jobs: list[Job] = field(default_factory=list)
    error: str = ""


def plan_search(query: SearchQuery, source_ids: list[str], budget_usd: float) -> list[PlannedRun]:
    """Reparte el presupuesto entre las fuentes elegidas y recorta lo que se pide a cada una para no pasarse."""
    chosen = [SOURCES[source_id] for source_id in source_ids if source_id in SOURCES]
    if not chosen:
        return []
    share = budget_usd / len(chosen)
    runs = []
    for source in chosen:
        limit = source.limit_for_budget(share, query.limit)
        runs.append(PlannedRun(source, limit, share, source.estimate_cost(limit)))
    return runs


def run_search(token: str, query: SearchQuery, runs: list[PlannedRun],
               runner: Callable[..., list[dict[str, Any]]] = run_actor,
               progress: Callable[[str], None] | None = None) -> list[SourceResult]:
    """Lanza cada fuente por separado: si una falla, las demás siguen y el error queda en su resultado."""
    results = []
    for planned in runs:
        if progress:
            progress(planned.source.name)
        outcome = SourceResult(planned.source)
        try:
            partial = SearchQuery(query.keywords, query.location, planned.limit, query.posted, query.remote)
            items = runner(token, planned.source.actor, planned.source.build_input(partial), planned.cap_usd)
            outcome.jobs = [job for item in items if (job := planned.source.parse_item(item)) is not None]
        except ApifyError as error:
            outcome.error = str(error)
        results.append(outcome)
    return results
