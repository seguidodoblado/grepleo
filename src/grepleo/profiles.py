"""Perfiles de búsqueda: lo que sabes y lo que buscas, contra lo que se evalúa cada oferta."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STUDIES = ("", "fp", "degree", "master")   # claves estables; el texto mostrado lo pone la interfaz
STUDIES_RANK = {"": 0, "fp": 1, "degree": 2, "master": 3}


def parse_term(spec: str) -> tuple[str, list[str]]:
    """«Power BI|powerbi|PBI» → («Power BI», [«Power BI», «powerbi», «PBI»]): el nombre y todo lo que lo nombra."""
    names = [part.strip() for part in spec.split("|") if part.strip()]
    if not names:
        return "", []
    return names[0], names


@dataclass
class Category:
    """Un tipo de oferta (por ejemplo «Data PO»): se asigna si su título o texto cita alguna de sus palabras."""
    name: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class Profile:
    name: str
    headline: str = ""
    years: int = 0
    studies: str = ""
    languages: dict[str, str] = field(default_factory=dict)   # {«Inglés»: «C1»}
    must: list[str] = field(default_factory=list)             # requisitos imprescindibles (con sinónimos)
    nice: list[str] = field(default_factory=list)             # requisitos deseables
    avoid: list[str] = field(default_factory=list)            # cosas que no quieres encontrar
    salary_min: int = 0                                       # euros brutos anuales; 0: no importa
    work_modes: list[str] = field(default_factory=list)       # remote, hybrid, onsite; vacío: cualquiera
    locations: list[str] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    notes: str = ""                                           # texto libre (lo usará la IA en una versión futura)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "headline": self.headline, "years": self.years, "studies": self.studies,
            "languages": dict(self.languages), "must": list(self.must), "nice": list(self.nice),
            "avoid": list(self.avoid), "salary_min": self.salary_min, "work_modes": list(self.work_modes),
            "locations": list(self.locations), "notes": self.notes,
            "categories": [{"name": c.name, "keywords": list(c.keywords)} for c in self.categories],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Tolerante: un campo que falte o tenga el tipo equivocado toma su valor por defecto."""
        def texts(key: str) -> list[str]:
            value = data.get(key)
            return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []

        def number(key: str) -> int:
            value = data.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

        languages = data.get("languages")
        categories = data.get("categories")
        return cls(
            name=str(data.get("name") or "").strip(),
            headline=str(data.get("headline") or ""),
            years=number("years"),
            studies=data.get("studies") if data.get("studies") in STUDIES else "",
            languages={str(k): str(v) for k, v in languages.items()} if isinstance(languages, dict) else {},
            must=texts("must"), nice=texts("nice"), avoid=texts("avoid"),
            salary_min=number("salary_min"),
            work_modes=[m for m in texts("work_modes") if m in ("remote", "hybrid", "onsite")],
            locations=texts("locations"),
            categories=[Category(str(c.get("name") or "").strip(), [str(k) for k in c.get("keywords", [])
                                                                    if str(k).strip()])
                        for c in categories if isinstance(c, dict) and str(c.get("name") or "").strip()]
            if isinstance(categories, list) else [],
            notes=str(data.get("notes") or ""),
        )


def split_lines(text: str) -> list[str]:
    """Las líneas no vacías de un cuadro de texto, sin espacios sobrantes."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def split_commas(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def parse_languages(text: str) -> dict[str, str]:
    """«Inglés C1, Francés B1, Alemán» → {«Inglés»: «C1», «Francés»: «B1», «Alemán»: «»}."""
    languages: dict[str, str] = {}
    for part in split_commas(text):
        words = part.split()
        if words and len(words[-1]) == 2 and words[-1][0].upper() in "ABC" and words[-1][1] in "12":
            languages[" ".join(words[:-1]) or words[-1]] = words[-1].upper() if len(words) > 1 else ""
        else:
            languages[part] = ""
    return languages


def format_languages(languages: dict[str, str]) -> str:
    return ", ".join(f"{name} {level}".strip() for name, level in languages.items())


def parse_categories(text: str) -> list[Category]:
    """Una línea por tipo, «Nombre: palabra, palabra»; sin palabras, el propio nombre es la palabra."""
    categories = []
    for line in split_lines(text):
        name, _separator, words = line.partition(":")
        name = name.strip()
        if name:
            categories.append(Category(name, split_commas(words) or [name]))
    return categories


def format_categories(categories: list[Category]) -> str:
    return "\n".join(f"{category.name}: {', '.join(category.keywords)}" for category in categories)
