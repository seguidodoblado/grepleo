"""InfoJobs (España), con el Actor `igolaizola/infojobs-scraper`.

InfoJobs solo da los requisitos mínimos de cada oferta, no su descripción completa: son fichas resumidas.
"""
from __future__ import annotations

from typing import Any

from ..models import Job, WorkMode
from ..textutil import detect_work_mode, normalize
from .base import SearchQuery, Source, parse_salary, short_date, to_text

PROVINCES = (
    "a-coruna", "alava-araba", "albacete", "alicante-alacant", "almeria", "asturias", "avila", "badajoz",
    "barcelona", "burgos", "caceres", "cadiz", "cantabria", "castellon-castello", "ceuta", "ciudad-real",
    "cordoba", "cuenca", "girona", "granada", "guadalajara", "guipuzcoa-gipuzkoa", "huelva", "huesca",
    "illes-balears", "jaen", "la-rioja", "las-palmas", "leon", "lleida", "lugo", "madrid", "malaga", "melilla",
    "murcia", "navarra", "ourense", "palencia", "pontevedra", "salamanca", "santa-cruz-de-tenerife", "segovia",
    "sevilla", "soria", "tarragona", "teruel", "toledo", "valencia-valencia", "valladolid", "vizcaya-bizkaia",
    "zamora", "zaragoza",
)
_SINCE = {"day": "last-24-hours", "week": "last-7-days", "month": "last-15-days"}


def province_slug(location: str) -> str:
    """El identificador de provincia de InfoJobs para un texto de ubicación, o «» si no es una provincia."""
    slug = normalize(location).strip().replace(" ", "-")
    if slug in PROVINCES:
        return slug
    matches = [province for province in PROVINCES if slug and slug in province.split("-")]
    return matches[0] if len(matches) == 1 else ""


class InfoJobs(Source):
    id = "infojobs"
    name = "InfoJobs"
    actor = "igolaizola/infojobs-scraper"
    start_cost = 0.001
    item_cost = 0.001

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        data: dict[str, Any] = {"query": query.keywords, "maxItems": query.limit,
                                "sortBy": "recent" if query.posted else "relevance"}
        if query.posted in _SINCE:
            data["sinceDate"] = _SINCE[query.posted]
        if query.location:
            if slug := province_slug(query.location):
                data["province"] = slug
            else:
                data["city"] = query.location
        if query.remote:
            data["teleworking"] = ["remote-only"]
        return data

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        identifier = to_text(item.get("id")) or to_text(item.get("link"))
        title = to_text(item.get("title"))
        if not identifier or not title:
            return None
        description = to_text(item.get("salaryDescription"))
        low, high = parse_salary(description)
        if low is None:
            low, high = parse_salary(" ".join(part for part in (to_text(item.get("salaryMin")),
                                                                  to_text(item.get("salaryMax")),
                                                                  to_text(item.get("salaryPeriod"))) if part))
        remote_text = to_text(item.get("teleworking"))
        place = ", ".join(part for part in (to_text(item.get("city")), to_text(item.get("province"))) if part)
        mode = detect_work_mode(remote_text) if remote_text else WorkMode.UNKNOWN
        return Job(
            key=f"{self.id}:{identifier}", source=self.id, title=title,
            company=to_text((item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else ""),
            location=place, work_mode=mode, contract=to_text(item.get("contractType")),
            salary_min=low, salary_max=high, salary_text=description,
            experience_text=to_text(item.get("experienceMin")), studies_text=to_text(item.get("study")),
            description=to_text(item.get("requirementMin")), full_description=False,
            url=to_text(item.get("link")), posted=short_date(item.get("published")),
        )
