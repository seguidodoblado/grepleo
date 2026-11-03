"""LinkedIn, con el Actor `valig/linkedin-jobs-scraper` (sin iniciar sesión ni cookies)."""
from __future__ import annotations

from typing import Any

from ..models import Job
from ..textutil import detect_work_mode
from .base import SearchQuery, Source, parse_salary, short_date, to_text
from .indeed import FULL_DESCRIPTION_CHARS

_POSTED = {"day": "r86400", "week": "r604800", "month": "r2592000"}


class LinkedIn(Source):
    id = "linkedin"
    name = "LinkedIn"
    actor = "valig/linkedin-jobs-scraper"
    start_cost = 0.001
    item_cost = 0.0004

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        data: dict[str, Any] = {"keywords": query.keywords, "location": query.location or "España",
                                "limit": query.limit}
        if query.posted in _POSTED:
            data["datePosted"] = _POSTED[query.posted]
        return data

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        identifier = to_text(item.get("id")) or to_text(item.get("url"))
        title = to_text(item.get("title"))
        if not identifier or not title:
            return None
        text = to_text(item.get("description"))
        salary = to_text(item.get("salary"))
        low, high = parse_salary(salary)
        work_type = to_text(item.get("workType"))
        return Job(
            key=f"{self.id}:{identifier}", source=self.id, title=title, company=to_text(item.get("companyName")),
            location=to_text(item.get("location")),
            work_mode=detect_work_mode(f"{work_type} {title}") if work_type else detect_work_mode(title),
            contract=to_text(item.get("contractType")), salary_min=low, salary_max=high, salary_text=salary,
            description=text, full_description=len(text) >= FULL_DESCRIPTION_CHARS,
            url=to_text(item.get("url")) or to_text(item.get("applyUrl")), posted=short_date(item.get("postedDate")),
        )
