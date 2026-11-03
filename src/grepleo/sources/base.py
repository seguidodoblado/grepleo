"""Lo común a todas las fuentes: la consulta, el contrato de una fuente y la normalización de salarios."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..models import Job

POSTED = ("", "day", "week", "month")   # claves estables; la interfaz muestra el texto

_HOURS_PER_YEAR = 1800
_MONTHS_PER_YEAR = 12
_ANNUALIZE = {"year": 1, "month": _MONTHS_PER_YEAR, "week": 52, "day": 220, "hour": _HOURS_PER_YEAR}


@dataclass
class SearchQuery:
    keywords: str
    location: str = ""
    limit: int = 50
    posted: str = ""
    remote: bool = False


class Source:
    """Una fuente de ofertas: sabe pedirle la búsqueda a su Actor de Apify y convertir lo que devuelve."""
    id = ""
    name = ""
    actor = ""            # «usuario/nombre» del Actor en Apify
    start_cost = 0.0      # dólares por arrancar el Actor (plan gratuito de Apify)
    item_cost = 0.0       # dólares por oferta

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        raise NotImplementedError

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        raise NotImplementedError

    def estimate_cost(self, limit: int) -> float:
        return self.start_cost + self.item_cost * limit

    def limit_for_budget(self, budget: float, wanted: int) -> int:
        """Cuántas ofertas se pueden pedir sin pasar del presupuesto (al menos una)."""
        if self.item_cost <= 0:
            return wanted
        affordable = int((budget - self.start_cost) / self.item_cost)
        return max(1, min(wanted, affordable))


def to_text(value: Any) -> str:
    """Un campo de un Actor como texto: acepta cadenas, números y objetos {«value»: …}."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("name") or value.get("text") or ""
    return "" if value is None else str(value).strip()


_UNIT_ALIASES = {"yearly": "year", "monthly": "month", "weekly": "week", "daily": "day", "hourly": "hour"}


def annual_euros(amount: float, unit: str) -> float:
    """Pasa un importe a euros brutos anuales según su unidad (YEAR, MONTH, HOUR…; sin unidad, el propio importe)."""
    key = unit.lower().strip()
    return amount * _ANNUALIZE.get(_UNIT_ALIASES.get(key, key), 1)


_NUMBER = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(k)?", re.IGNORECASE)


def _unit_in(text: str) -> str:
    lowered = text.lower()
    for unit, pattern in (("hour", r"hora|hour|/h\b|/hr"), ("month", r"mes|month|/mo\b|mensual"),
                          ("week", r"semana|week"), ("year", r"a[nñ]o|year|/yr|anual|annual|bruto")):
        if re.search(pattern, lowered):
            return unit
    return ""


def parse_salary(text: str) -> tuple[float | None, float | None]:
    """Mínimo y máximo anuales (euros) de un texto de salario: «30.000 € - 40.000 € Bruto/año», «€30K/yr»…"""
    if not text or not any(char.isdigit() for char in text):
        return None, None
    unit = _unit_in(text)
    values: list[float] = []
    for match in _NUMBER.finditer(text):
        raw = match.group(1)
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
            number = float(re.sub(r"[.,]", "", raw))
        else:
            number = float(raw.replace(",", "."))
        if match.group(2):
            number *= 1000
        values.append(number)
    values = [value for value in values if value > 0]
    if not values:
        return None, None
    if not unit:
        unit = "year" if max(values) >= 12000 else "month" if max(values) >= 1000 else ""
        if not unit:
            return None, None
    annual = [annual_euros(value, unit) for value in values[:2]]
    return min(annual), max(annual)


def short_date(value: Any) -> str:
    """La fecha de una oferta como «AAAA-MM-DD» si el texto la trae al principio."""
    text = to_text(value)
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else text
