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


MIN_AXES, MAX_AXES = 3, 8          # un radar necesita entre 3 y 8 elementos para ser legible
DEFAULT_LEVEL = 5
# nivel (0 a 10) de una habilidad que no tiene uno propio: lo que se daba a las listas «dominas» y «conoces» antes de que cada
# habilidad tuviera el suyo (los perfiles antiguos se migran con estos valores o con el nivel técnico general que tuvieran)
MASTER_LEVEL, KNOW_LEVEL, SOFT_MASTER_LEVEL, SOFT_KNOW_LEVEL = 10, 7, 8, 7
DOMINANT_FROM = 7   # desde este nivel una habilidad cuenta como «que dominas»; por debajo, «que conoces»


def skill_key(spec: str) -> str:
    """La clave de una habilidad en `Profile.skill_levels`: su nombre, en minúsculas y sin tildes."""
    from .textutil import normalize
    return normalize(parse_term(spec)[0])


@dataclass
class RadarAxis:
    """Un elemento de un radar: algo que aparece en las ofertas (con sinónimos) y tu nivel de 0 a 10 en ello."""
    spec: str                   # «AWS|amazon web services»
    level: int = DEFAULT_LEVEL

    @property
    def name(self) -> str:
        return parse_term(self.spec)[0]


@dataclass
class SkillRadar:
    """Un radar de un tema (Cloud, Lenguajes, Metodologías…): sus elementos son los ejes."""
    name: str
    axes: list[RadarAxis] = field(default_factory=list)


def parse_axes(text: str) -> list[RadarAxis]:
    """«AWS|amazon web services = 8», uno por línea → ejes. Sin «= nivel» (o con uno que no es un entero de 0 a 10)
    el nivel es 5."""
    axes = []
    for line in text.splitlines():
        spec, _separator, level = line.rpartition("=") if "=" in line else (line, "", "")
        spec = spec.strip()
        if not parse_term(spec)[0]:
            continue
        digits = level.strip()
        axes.append(RadarAxis(spec, int(digits) if digits.isdigit() and 0 <= int(digits) <= 10 else DEFAULT_LEVEL))
    return axes


def format_axes(axes: list[RadarAxis]) -> str:
    return "\n".join(f"{axis.spec} = {axis.level}" for axis in axes)


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
    must: list[str] = field(default_factory=list)             # habilidades técnicas que dominas (con sinónimos)
    nice: list[str] = field(default_factory=list)             # habilidades técnicas que conoces
    soft_must: list[str] = field(default_factory=list)        # habilidades blandas que dominas
    soft_nice: list[str] = field(default_factory=list)        # habilidades blandas que conoces
    avoid: list[str] = field(default_factory=list)            # cosas que no quieres encontrar
    salary_min: int = 0                                       # euros brutos anuales; 0: no importa
    work_modes: list[str] = field(default_factory=list)       # remote, hybrid, onsite; vacío: cualquiera
    locations: list[str] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    notes: str = ""                                           # texto libre (lo usará la IA en una versión futura)
    full_name: str = ""                                       # datos para el currículum (todo se queda en tu equipo)
    email: str = ""
    phone: str = ""
    networks: dict[str, str] = field(default_factory=dict)    # tus perfiles profesionales: {«github»: «github.com/ana»}
    links: str = ""                                           # otros enlaces, uno por línea
    experience: str = ""                                      # experiencia profesional: puestos, empresas, fechas, logros
    education: str = ""                                       # formación detallada (centros, titulaciones, cursos)
    cv_file: str = ""                                         # ruta de un CV propio ya hecho (PDF, Word, texto…)
    radars: list[SkillRadar] = field(default_factory=list)    # tus radares por temas, con sus propios elementos
    skill_levels: dict[str, int] = field(default_factory=dict)   # tu nivel (0 a 10) en cada habilidad de las listas, por `skill_key`

    def level_of(self, spec: str, default: int) -> int:
        """El nivel de una habilidad de las listas: el suyo, o `default` si aún no se le ha puesto uno."""
        return self.skill_levels.get(skill_key(spec), default)

    def technical_levels(self) -> list[tuple[str, int]]:
        """Tus habilidades técnicas de las listas con su nivel."""
        return [*((spec, self.level_of(spec, MASTER_LEVEL)) for spec in self.must),
                *((spec, self.level_of(spec, KNOW_LEVEL)) for spec in self.nice)]

    def soft_levels(self) -> list[tuple[str, int]]:
        """Tus habilidades blandas con su nivel."""
        return [*((spec, self.level_of(spec, SOFT_MASTER_LEVEL)) for spec in self.soft_must),
                *((spec, self.level_of(spec, SOFT_KNOW_LEVEL)) for spec in self.soft_nice)]

    @property
    def all_must(self) -> list[str]:
        """Todos los imprescindibles: técnicos y blandos."""
        return [*self.must, *self.soft_must]

    @property
    def all_nice(self) -> list[str]:
        """Todos los deseables: técnicos y blandos."""
        return [*self.nice, *self.soft_nice]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "headline": self.headline, "years": self.years, "studies": self.studies,
            "languages": dict(self.languages), "must": list(self.must), "nice": list(self.nice),
            "soft_must": list(self.soft_must), "soft_nice": list(self.soft_nice),
            "avoid": list(self.avoid), "salary_min": self.salary_min, "work_modes": list(self.work_modes),
            "locations": list(self.locations), "notes": self.notes, "skill_levels": dict(self.skill_levels),
            "radars": [{"name": radar.name, "axes": [{"spec": axis.spec, "level": axis.level} for axis in radar.axes]}
                       for radar in self.radars],
            "full_name": self.full_name, "email": self.email, "phone": self.phone, "links": self.links,
            "networks": dict(self.networks),
            "experience": self.experience, "education": self.education, "cv_file": self.cv_file,
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

        networks = data.get("networks")
        radars = []
        for item in data.get("radars") if isinstance(data.get("radars"), list) else []:
            if not isinstance(item, dict) or not str(item.get("name") or "").strip():
                continue
            axes = [RadarAxis(str(axis.get("spec") or "").strip(), axis.get("level")
                              if isinstance(axis.get("level"), int) and not isinstance(axis.get("level"), bool)
                              and 0 <= axis.get("level") <= 10 else DEFAULT_LEVEL)
                    for axis in item.get("axes", []) if isinstance(axis, dict) and str(axis.get("spec") or "").strip()]
            radars.append(SkillRadar(str(item["name"]).strip(), axes[:MAX_AXES]))
        languages = data.get("languages")
        categories = data.get("categories")
        return cls(
            name=str(data.get("name") or "").strip(),
            headline=str(data.get("headline") or ""),
            years=number("years"),
            studies=data.get("studies") if data.get("studies") in STUDIES else "",
            languages={str(k): str(v) for k, v in languages.items()} if isinstance(languages, dict) else {},
            must=texts("must"), nice=texts("nice"), soft_must=texts("soft_must"), soft_nice=texts("soft_nice"),
            avoid=texts("avoid"),
            salary_min=number("salary_min"),
            work_modes=[m for m in texts("work_modes") if m in ("remote", "hybrid", "onsite")],
            locations=texts("locations"),
            categories=[Category(str(c.get("name") or "").strip(), [str(k) for k in c.get("keywords", [])
                                                                    if str(k).strip()])
                        for c in categories if isinstance(c, dict) and str(c.get("name") or "").strip()]
            if isinstance(categories, list) else [],
            notes=str(data.get("notes") or ""),
            full_name=str(data.get("full_name") or ""), email=str(data.get("email") or ""),
            phone=str(data.get("phone") or ""), links=str(data.get("links") or ""),
            networks={str(k): str(v).strip() for k, v in networks.items() if str(v).strip()}
            if isinstance(networks, dict) else {},
            experience=str(data.get("experience") or ""), education=str(data.get("education") or ""),
            cv_file=str(data.get("cv_file") or ""), radars=radars,
            skill_levels=_skill_levels(data),
        )


def _skill_levels(data: dict[str, Any]) -> dict[str, int]:
    """Los niveles por habilidad. Un perfil antiguo, sin ellos, se migra con lo que contaban hasta ahora: lo que
    dominabas con tu nivel técnico general (10 si no lo habías tocado), lo que conocías con el 70 % de él y las blandas
    con 8 y 7; así las ofertas puntúan igual antes y después."""
    stored = data.get("skill_levels")
    if isinstance(stored, dict):
        return {str(k): v for k, v in stored.items() if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 10}

    def names(key: str) -> list[str]:
        value = data.get(key)
        return [skill_key(str(item)) for item in value if skill_key(str(item))] if isinstance(value, list) else []

    old = data.get("radar")
    general = old.get("technical") if isinstance(old, dict) else None
    general = general if isinstance(general, int) and not isinstance(general, bool) and 0 <= general <= 10 else 10
    levels: dict[str, int] = {}
    for key in names("nice"):
        levels[key] = round(general * 0.7)
    for key in names("must"):
        levels[key] = general
    for key in names("soft_nice"):
        levels[key] = SOFT_KNOW_LEVEL
    for key in names("soft_must"):
        levels[key] = SOFT_MASTER_LEVEL
    return levels


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


def is_level(text: str) -> bool:
    """Si el texto es solo un nivel del Marco Común Europeo (A1 a C2)."""
    return len(text) == 2 and text[0].upper() in "ABC" and text[1] in "12"


def bare_levels(text: str) -> list[str]:
    """Los niveles sueltos que se han escrito sin idioma («A2» en vez de «Inglés A2»): se guardarían como un idioma que
    se llama «A2» y ninguna oferta lo pediría."""
    return [part for part in split_commas(text) if is_level(part.strip())]


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


def link_list(text: str) -> list[str]:
    """Los enlaces de un perfil: uno por línea. Un perfil antiguo que los tenga en una sola línea, separados por comas,
    se lee igual."""
    items = []
    for line in text.splitlines():
        items.extend(part.strip() for part in line.split(",") if part.strip())
    return items


def format_categories(categories: list[Category]) -> str:
    return "\n".join(f"{category.name}: {', '.join(category.keywords)}" for category in categories)
