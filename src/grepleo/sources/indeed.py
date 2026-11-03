"""Indeed, con el Actor `valig/indeed-jobs-scraper`."""
from __future__ import annotations

from typing import Any

from ..models import Job
from ..textutil import detect_work_mode
from .base import SearchQuery, Source, annual_euros, short_date, to_text

_POSTED = {"day": "1", "week": "7", "month": "14"}
FULL_DESCRIPTION_CHARS = 150   # una descripción más corta es un resumen


class Indeed(Source):
    id = "indeed"
    name = "Indeed"
    actor = "valig/indeed-jobs-scraper"
    start_cost = 0.001
    item_cost = 0.0001

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        location = query.location or ("remote" if query.remote else "")
        data: dict[str, Any] = {"country": "es", "title": query.keywords, "limit": query.limit}
        if location:
            data["location"] = location
        if query.posted in _POSTED:
            data["datePosted"] = _POSTED[query.posted]
        return data

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        identifier = to_text(item.get("key")) or to_text(item.get("jobUrl")) or to_text(item.get("url"))
        title = to_text(item.get("title"))
        if not identifier or not title:
            return None
        employer = item.get("employer") if isinstance(item.get("employer"), dict) else {}
        place = item.get("location") if isinstance(item.get("location"), dict) else {}
        description = item.get("description")
        text = to_text(description.get("text") if isinstance(description, dict) else description)
        salary = item.get("baseSalary") if isinstance(item.get("baseSalary"), dict) else {}
        low = high = None
        currency = to_text(salary.get("currencyCode")) or "EUR"
        if currency.upper() == "EUR":
            unit = to_text(salary.get("unitOfWork"))
            low = annual_euros(salary["min"], unit) if isinstance(salary.get("min"), (int, float)) else None
            high = annual_euros(salary["max"], unit) if isinstance(salary.get("max"), (int, float)) else None
        types = item.get("jobTypes")
        types_text = ", ".join(str(label) for label in types.values()) if isinstance(types, dict) else ""
        city = to_text(place.get("city"))
        return Job(
            key=f"{self.id}:{identifier}", source=self.id, title=title,
            company=to_text(employer.get("name")), location=city, work_mode=detect_work_mode(f"{title} {types_text}"
                                                                                           f" {text[:600]}"),
            contract=types_text, salary_min=low, salary_max=high,
            salary_text="" if low is None else f"{low:,.0f}–{(high or low):,.0f} €".replace(",", "."),
            description=text, full_description=len(text) >= FULL_DESCRIPTION_CHARS,
            url=to_text(item.get("jobUrl")) or to_text(item.get("url")), posted=short_date(item.get("datePublished")),
            closed=bool(item.get("expired")),
        )
