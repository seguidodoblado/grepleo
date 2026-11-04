"""Tecnoempleo (España, empleo tecnológico), con el Actor `blackfalcondata/tecnoempleo-scraper`.

Con `includeDetails` el Actor trae la descripción completa, el salario ya desglosado y las tecnologías de la oferta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import Job, WorkMode
from ..textutil import detect_work_mode, normalize
from .base import SearchQuery, Source, annual_euros, short_date, to_text

FULL_DESCRIPTION_CHARS = 150   # una descripción más corta es un resumen
_REMOTE = "1"                  # valores de `en_remoto` del Actor (comprobados con ejecuciones reales)
_SINCE_DAYS = {"day": 1, "week": 7, "month": 30}
_ARRANGEMENT = {"ONSITE": WorkMode.ONSITE, "HYBRID": WorkMode.HYBRID, "REMOTE": WorkMode.REMOTE}


class Tecnoempleo(Source):
    id = "tecnoempleo"
    name = "Tecnoempleo"
    actor = "blackfalcondata/tecnoempleo-scraper"
    start_cost = 0.01
    item_cost = 0.0015

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        data: dict[str, Any] = {"query": query.keywords, "maxResults": query.limit, "includeDetails": True,
                                "descriptionFormat": "text", "excludeEmptyFields": True}
        if query.remote:
            data["en_remoto"] = _REMOTE   # un puesto 100 % remoto no tiene provincia
        elif query.location:
            data["province"] = query.location
        if query.posted in _SINCE_DAYS:
            since = datetime.now(timezone.utc).date() - timedelta(days=_SINCE_DAYS[query.posted])
            data["date_start"] = since.isoformat()
        return data

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        identifier = to_text(item.get("jobId")) or to_text(item.get("url"))
        title = to_text(item.get("title"))
        if not identifier or not title:
            return None
        text = to_text(item.get("descriptionText")) or to_text(item.get("description"))
        technologies = [to_text(name).rstrip(".") for name in item.get("technologies") or [] if to_text(name)]
        if technologies:   # las etiquetas de tecnologías de la oferta cuentan como parte de su texto
            text = f"{text}\n\nTecnologías: {', '.join(technologies)}".strip()
        low, high = self._salary(item)
        location = to_text(item.get("location"))
        return Job(
            key=f"{self.id}:{identifier}", source=self.id, title=title, company=to_text(item.get("company")),
            location=location, work_mode=self._work_mode(item, title, text),
            contract=to_text(item.get("contractType")), salary_min=low, salary_max=high,
            salary_text=self._salary_text(low, high, to_text(item.get("salaryText"))), experience_text=to_text(item.get("experienceLevel")),
            studies_text=to_text(item.get("educationLevel")), description=text,
            full_description=bool(item.get("detailFetched")) and len(text) >= FULL_DESCRIPTION_CHARS,
            url=to_text(item.get("url")) or to_text(item.get("applyUrl")),
            posted=short_date(item.get("publishDateISO") or item.get("publishDate")),
        )

    @staticmethod
    def _salary_text(low: float | None, high: float | None, raw: str) -> str:
        """El salario como en las demás fuentes («36.000–48.000 €»); sin cifras, el texto del portal."""
        if low is None:
            return raw
        return f"{low:,.0f}–{(high or low):,.0f} €".replace(",", ".")

    @staticmethod
    def _salary(item: dict[str, Any]) -> tuple[float | None, float | None]:
        if to_text(item.get("salaryCurrency")).upper() not in ("", "EUR"):
            return None, None
        unit = to_text(item.get("salaryPeriod")).lower() or "year"

        def annual(key: str) -> float | None:
            value = item.get(key)
            number = isinstance(value, (int, float)) and not isinstance(value, bool)
            return annual_euros(value, unit) if number else None

        low, high = annual("salaryMin"), annual("salaryMax")
        return low if low is not None else high, high if high is not None else low

    @staticmethod
    def _work_mode(item: dict[str, Any], title: str, text: str) -> WorkMode:
        mode = _ARRANGEMENT.get(to_text(item.get("workArrangement")).upper())
        if mode:
            return mode
        place = normalize(f"{to_text(item.get('location'))} {to_text(item.get('province'))}")
        if "remoto" in place:   # los remotos llegan sin `workArrangement` y con «100% remoto» de ubicación
            return WorkMode.REMOTE
        return detect_work_mode(f"{title} {text[:600]}")
