"""InfoJobs (España), con el Actor `unfenced-group/infojobs-net-scraper`.

InfoJobs bloquea las peticiones directas con un muro anti-bot, por eso se usa un Actor. Con `fetchDetails` el Actor trae la
**descripción completa** de cada oferta, el salario ya desglosado y la modalidad de trabajo, así que ya no son fichas
resumidas. No tiene filtro de «solo remoto»: se aplica aquí, sobre lo que devuelve.
"""
from __future__ import annotations

from typing import Any

from ..models import Job, WorkMode
from ..textutil import detect_work_mode
from .base import SearchQuery, Source, annual_euros, short_date, to_text

FULL_DESCRIPTION_CHARS = 150   # una descripción más corta es un resumen
_SINCE_DAYS = {"day": 1, "week": 7, "month": 30}   # los valores que acepta el Actor son 1, 7, 15 y 30
_MODES = {"remote": WorkMode.REMOTE, "hybrid": WorkMode.HYBRID, "on-site": WorkMode.ONSITE, "onsite": WorkMode.ONSITE}


class InfoJobs(Source):
    id = "infojobs"
    name = "InfoJobs"
    actor = "unfenced-group/infojobs-net-scraper"
    start_cost = 0.00005
    item_cost = 0.00079

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        data: dict[str, Any] = {"searchQuery": query.keywords, "maxItems": query.limit, "fetchDetails": True}
        if query.location:
            data["location"] = query.location
        if query.posted in _SINCE_DAYS:
            data["daysOld"] = _SINCE_DAYS[query.posted]
        return data

    def refine(self, jobs: list[Job], query: SearchQuery) -> list[Job]:
        """El Actor no filtra por «solo remoto»: se descartan aquí las ofertas que no lo son."""
        return [job for job in jobs if job.work_mode is WorkMode.REMOTE] if query.remote else jobs

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        identifier = to_text(item.get("id")) or to_text(item.get("url"))
        title = to_text(item.get("title"))
        if not identifier or not title:
            return None
        text = to_text(item.get("descriptionText")) or to_text(item.get("descriptionMarkdown"))
        low, high = self._salary(item)
        mode = _MODES.get(to_text(item.get("workMode")).lower())
        if mode is None:
            mode = detect_work_mode(f"{title} {text[:600]}")
        place = to_text(item.get("city")) or to_text(item.get("location"))
        return Job(
            key=f"{self.id}:{identifier}", source=self.id, title=title, company=to_text(item.get("company")),
            location=place, work_mode=mode, contract=to_text(item.get("contractType")),
            salary_min=low, salary_max=high, salary_text=self._salary_text(low, high), description=text,
            full_description=len(text) >= FULL_DESCRIPTION_CHARS,
            url=to_text(item.get("url")) or to_text(item.get("applyUrl")),
            posted=short_date(item.get("publishDateISO") or item.get("publishDate")),
        )

    @staticmethod
    def _salary(item: dict[str, Any]) -> tuple[float | None, float | None]:
        if to_text(item.get("salaryCurrency")).upper() not in ("", "EUR"):
            return None, None
        unit = to_text(item.get("salaryPeriod")) or "year"

        def annual(key: str) -> float | None:
            value = item.get(key)
            number = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
            return annual_euros(value, unit) if number else None

        low, high = annual("salaryMin"), annual("salaryMax")
        return low if low is not None else high, high if high is not None else low

    @staticmethod
    def _salary_text(low: float | None, high: float | None) -> str:
        """El salario como en las demás fuentes («28.000–36.000 €»); sin cifras, vacío."""
        if low is None:
            return ""
        return f"{low:,.0f}–{(high or low):,.0f} €".replace(",", ".")
