"""Los radares de competencias: lo que tú tienes frente a lo que pide una oferta, en ejes comparables.

Hay un radar general de cinco ejes (técnicas, blandas, experiencia, idiomas y estudios) y los radares por temas que
define cada perfil (Cloud, Lenguajes…), cuyos ejes son cosas concretas que aparecen en las ofertas. Los dos polígonos
de cada radar usan la misma escala de 0 a 10, de modo que donde el tuyo cubre al de la oferta, cumples; el solape es
cuánto de lo que pide la oferta cubres. Sin GTK.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .detail import BULLET, HEADING, structure_description
from .i18n import _, ngettext
from .models import Job
from .panorama import DEFAULT_CATALOG
from .profiles import MAX_AXES, MIN_AXES, STUDIES_RANK, Profile, RadarAxis, SkillRadar, parse_term
from .textutil import (
    LEVELS,
    language_requirements,
    level_rank,
    mentions,
    normalize,
    required_years,
    studies_in_description,
    studies_rank,
    term_pattern,
)

SCALE = 10.0
AXES = ("technical", "soft", "experience", "languages", "studies")   # claves estables; la interfaz muestra el texto

SOFT_VOCABULARY = (
    "trabajo en equipo|teamwork|team player", "liderazgo|leadership", "comunicación|communication",
    "proactividad|proactive|proactivo", "autonomía|autonomy|autonomous", "resolución de problemas|problem solving",
    "adaptabilidad|adaptability|capacidad de adaptación", "organización|organization|organisation",
    "orientación a resultados|results.?oriented", "orientación al cliente|customer focus",
    "pensamiento crítico|critical thinking", "creatividad|creativity", "empatía|empathy",
    "gestión del tiempo|time management", "negociación|negotiation", "capacidad analítica|analytical skills",
    "iniciativa|initiative", "colaboración|collaboration", "flexibilidad|flexibility", "compromiso|commitment",
    "atención al detalle|attention to detail", "aprendizaje continuo|continuous learning",
)


def clamp(value: float) -> float:
    return max(0.0, min(SCALE, value))


def _hits(text: str, specs: list[str]) -> int:
    """Cuántos de estos requisitos (con sinónimos) cita el texto, cada uno una sola vez."""
    normalized = normalize(text)
    return sum(1 for spec in specs if (names := parse_term(spec)[1]) and mentions(normalized, names))


def default_levels(profile: Profile) -> dict[str, float]:
    """Tu radar calculado con los datos del perfil: una habilidad = un punto (las blandas, dos) y el resto por escala."""
    best_language = max((level_rank(level) for level in profile.languages.values()), default=0)
    return {
        "technical": clamp(len({*profile.must, *profile.nice})),
        "soft": clamp(2 * len({*profile.soft_must, *profile.soft_nice})),
        "experience": clamp(profile.years),
        "languages": clamp(best_language * SCALE / len(LEVELS)),
        "studies": clamp(STUDIES_RANK[profile.studies] * SCALE / 3),
    }


def profile_levels(profile: Profile) -> dict[str, float]:
    """Tu radar: lo que has fijado a mano en el perfil y, donde no, lo que salen de sus datos."""
    levels = default_levels(profile)
    levels.update({axis: clamp(float(value)) for axis, value in profile.radar.items() if axis in AXES})
    return levels


def offer_demand(job: Job, profile: Profile) -> dict[str, float | None]:
    """Lo que pide la oferta en cada eje; None si no se puede saber (una ficha resumida no demuestra que no pida algo)."""
    full = job.full_description
    catalog = [spec for spec in DEFAULT_CATALOG if normalize(parse_term(spec)[0]) != "ingles"]   # el inglés es un idioma
    technical = [*catalog, *profile.must, *profile.nice]
    soft = [*SOFT_VOCABULARY, *profile.soft_must, *profile.soft_nice]
    years = required_years(job.experience_text) if job.experience_text else None
    if years is None:
        years = required_years(job.text, strict=True)
    studies = studies_rank(job.studies_text) if job.studies_text else None
    if studies is None and full:
        studies = studies_in_description(job.text)[0]
    languages = language_requirements(job.text)
    # un idioma pedido sin nivel cuenta como nivel medio (B1)
    top_language = max((level_rank(level) or 3 for level in languages.values()), default=0)
    return {
        "technical": clamp(_hits(job.text, technical)) if full else None,
        "soft": clamp(2 * _hits(job.text, soft)) if full else None,
        "experience": clamp(years) if years is not None else None,
        "languages": clamp(top_language * SCALE / len(LEVELS)) if (full or languages) else None,
        "studies": clamp(studies * SCALE / 3) if studies is not None else (0.0 if full else None),
    }


MIN_DRAWN = 1.2   # radio mínimo al dibujar: con 0 o «?» el vértice caería en el centro y el polígono se colapsaría


def drawn_value(value: float | None) -> float:
    """El valor con el que se dibuja un vértice: nunca menos que `MIN_DRAWN`, para que el radar sea siempre un polígono
    completo (pentágono, hexágono…) y se vea el área que se solapa. El valor real sigue en el tooltip y en el solape."""
    return max(MIN_DRAWN, min(SCALE, value or 0.0))


def polygon_points(values: list[float], center_x: float, center_y: float, radius: float) -> list[tuple[float, float]]:
    """Los vértices del polígono de un radar: el primer eje arriba y los demás en el sentido de las agujas del reloj."""
    points = []
    for index, value in enumerate(values):
        angle = -math.pi / 2 + 2 * math.pi * index / len(values)
        distance = radius * max(0.0, min(SCALE, value)) / SCALE
        points.append((center_x + distance * math.cos(angle), center_y + distance * math.sin(angle)))
    return points


def axis_labels() -> dict[str, str]:
    return {"technical": _("Técnicas"), "soft": _("Blandas"), "experience": _("Experiencia"),
            "languages": _("Idiomas"), "studies": _("Estudios")}


# --- lo que pide la oferta de un elemento concreto -------------------------------------------------------
DEMAND_REQUIRED, DEMAND_NICE, DEMAND_MENTIONED = 10.0, 7.0, 5.0
_NICE_CUE = re.compile(r"valor|desea|nice to have|\bplus\b|bonus|opcional|preferibl|se aprecia|ideal|\bsuma\b")
_REQUIRED_CUE = re.compile(r"imprescind|indispensable|obligatori|requisit|requirement|necesari|\bmust\b|"
                           r"se requiere|minim|excluyente|buscamos|qualification")


def _cue_of(normalized: str) -> float | None:
    """Lo que dice un título o una frase (ya normalizados) sobre lo que sigue: deseable (7), imprescindible (10) o
    nada (None)."""
    if _NICE_CUE.search(normalized):   # «requisitos deseables» es deseable: lo suave gana a lo duro
        return DEMAND_NICE
    return DEMAND_REQUIRED if _REQUIRED_CUE.search(normalized) else None


@lru_cache(maxsize=512)
def _prepared(description: str) -> tuple[tuple[bool, float | None, str, float | None], ...]:
    """La descripción troceada y normalizada una sola vez: (es título, lo que dice el título, texto normalizado, lo que
    dice la propia línea). Se consulta una vez por cada elemento de cada radar y de la estimación ATS."""
    prepared = []
    for block in structure_description(description):
        normalized = normalize(block.text)
        if block.kind == HEADING:
            prepared.append((True, _cue_of(normalized), "", None))
        else:
            own = _cue_of(normalized) if block.kind == BULLET or len(block.text) < 200 else None
            prepared.append((False, None, normalized, own))
    return tuple(prepared)


@lru_cache(maxsize=1024)
def _patterns(spec: str) -> tuple[re.Pattern[str], ...]:
    """Las expresiones que buscan un elemento y sus sinónimos en un texto ya normalizado."""
    return tuple(term_pattern(name) for name in parse_term(spec)[1] if name.strip())


@lru_cache(maxsize=2048)
def _normalized(text: str) -> str:
    return normalize(text)


def term_demand(job: Job, spec: str) -> float | None:
    """Cuánto pide la oferta un elemento: 10 si lo cita como requisito o en el título, 7 como deseable, 5 si solo lo
    menciona, 0 si no aparece y None si no se puede saber (ficha resumida que no lo cita)."""
    patterns = _patterns(spec)
    if not patterns:
        return None
    title = _normalized(job.title)
    if any(pattern.search(title) for pattern in patterns):
        return DEMAND_REQUIRED
    if not job.full_description:
        return None
    best, section = 0.0, DEMAND_MENTIONED
    for is_heading, heading_cue, normalized, own in _prepared(job.description):
        if is_heading:
            section = heading_cue or DEMAND_MENTIONED
        elif any(pattern.search(normalized) for pattern in patterns):
            best = max(best, own or section)
    return best


# --- radares listos para dibujar ---------------------------------------------------------------------
@dataclass
class RadarData:
    title: str
    labels: list[str]
    levels: list[float]                  # tu nivel en cada eje
    demand: list[float | None]           # lo que pide la oferta; None: no se puede saber
    notes: list[str] = field(default_factory=list)   # por eje, con palabras: qué hay detrás del valor que pide la oferta

    @property
    def overlap(self) -> float | None:
        """De 0 a 1: cuánto de lo que pide la oferta cubres. None si la oferta no pide nada medible aquí."""
        return overlap(self.levels, self.demand)


def overlap(levels: list[float], demand: list[float | None]) -> float | None:
    asked = [(have, want) for have, want in zip(levels, demand, strict=True) if want]
    total = sum(want for _have, want in asked)
    return sum(min(have, want) for have, want in asked) / total if total else None


# --- la leyenda de un radar ----------------------------------------------------------------------------
COVERED, MISSING, NOT_ASKED, UNKNOWN = "covered", "missing", "not_asked", "unknown"


@dataclass
class LegendRow:
    label: str
    mine: float
    asked: float | None
    note: str                 # qué hay detrás de lo que pide la oferta
    status: str               # COVERED, MISSING, NOT_ASKED o UNKNOWN
    gap: float = 0.0          # cuánto te falta (solo si MISSING)


def legend_rows(radar: RadarData) -> list[LegendRow]:
    """Eje por eje: lo tuyo, lo que pide la oferta y si lo cubres."""
    rows = []
    for index, label in enumerate(radar.labels):
        mine, asked = radar.levels[index], radar.demand[index]
        note = radar.notes[index] if index < len(radar.notes) else ""
        if asked is None:
            rows.append(LegendRow(label, mine, None, note, UNKNOWN))
        elif asked <= 0:
            rows.append(LegendRow(label, mine, asked, note, NOT_ASKED))
        elif mine >= asked:
            rows.append(LegendRow(label, mine, asked, note, COVERED))
        else:
            rows.append(LegendRow(label, mine, asked, note, MISSING, asked - mine))
    return rows


def coverage_points(radar: RadarData) -> tuple[float, float]:
    """(lo que cubres, lo que pide la oferta) en puntos de la escala 0–10: la cuenta que hay detrás del solape."""
    asked = [(have, want) for have, want in zip(radar.levels, radar.demand, strict=True) if want]
    return sum(min(have, want) for have, want in asked), sum(want for _have, want in asked)


def main_gaps(radar: RadarData, limit: int = 3) -> list[LegendRow]:
    """Los ejes que más te faltan, de más a menos."""
    return sorted((row for row in legend_rows(radar) if row.status == MISSING), key=lambda row: -row.gap)[:limit]


def total_overlap(radars: list[RadarData]) -> float | None:
    """El solape de todos los radares juntos: cada elemento pesa lo que la oferta lo pide."""
    levels = [value for radar in radars for value in radar.levels]
    demand = [value for radar in radars for value in radar.demand]
    return overlap(levels, demand)


def known_axes(radars: list[RadarData]) -> tuple[int, int]:
    """Cuántos ejes se han podido medir en la oferta y cuántos hay en total: con pocos, el solape es poco fiable."""
    demand = [value for radar in radars for value in radar.demand]
    return sum(1 for value in demand if value is not None), len(demand)


def demand_note(value: float | None) -> str:
    """Qué significa lo que pide la oferta de un elemento: la escala de `term_demand` dicha con palabras."""
    if value is None:
        return _("ficha resumida: no se puede saber")
    if value >= DEMAND_REQUIRED:
        return _("la pide como requisito o en el título")
    if value >= DEMAND_NICE:
        return _("la valora como deseable")
    if value >= DEMAND_MENTIONED:
        return _("solo la menciona")
    return _("no aparece en la oferta")


def _general_notes(asked: dict[str, float | None]) -> list[str]:
    """Qué hay detrás de cada eje del radar general: tecnologías citadas, años pedidos, nivel de idioma…"""
    unknown = _("ficha resumida: no se puede saber")
    notes = []
    for axis in AXES:
        value = asked[axis]
        if value is None and axis == "experience":   # puede haber descripción completa que no diga los años
            notes.append(_("no dice cuánta experiencia pide"))
        elif value is None:
            notes.append(unknown)
        elif axis == "technical":
            if round(value) >= SCALE:   # el eje se corta en 10: no se sabe si son diez o más
                notes.append(_("cita {count} o más tecnologías").format(count=round(SCALE)))
            else:
                notes.append(ngettext("cita {count} tecnología", "cita {count} tecnologías", round(value))
                             .format(count=round(value)))
        elif axis == "soft":
            notes.append(ngettext("cita {count} habilidad blanda", "cita {count} habilidades blandas", round(value / 2))
                         .format(count=round(value / 2)))
        elif axis == "experience":
            notes.append(ngettext("pide {count} año de experiencia", "pide {count} años de experiencia", round(value))
                         .format(count=round(value)))
        elif axis == "languages":
            level = round(value * len(LEVELS) / SCALE)
            notes.append(_("pide nivel {level}").format(level=LEVELS[level - 1]) if level else _("no pide idiomas"))
        else:
            names = {1: _("FP"), 2: _("grado"), 3: _("máster")}
            rank = round(value * 3 / SCALE)
            notes.append(_("pide {level}").format(level=names[rank]) if rank else _("no pide estudios concretos"))
    return notes


def general_radar(job: Job, profile: Profile) -> RadarData:
    mine, asked = profile_levels(profile), offer_demand(job, profile)
    labels = axis_labels()
    return RadarData(_("General"), [labels[axis] for axis in AXES], [mine[axis] for axis in AXES],
                     [asked[axis] for axis in AXES], _general_notes(asked))


def topic_radar(job: Job, radar: SkillRadar) -> RadarData | None:
    axes = [axis for axis in radar.axes if axis.name][:MAX_AXES]
    if len(axes) < MIN_AXES:
        return None
    demand = [term_demand(job, axis.spec) for axis in axes]
    return RadarData(radar.name, [axis.name for axis in axes], [float(axis.level) for axis in axes], demand,
                     [demand_note(value) for value in demand])


def build_radars(job: Job, profile: Profile) -> list[RadarData]:
    """El radar general y, después, los del perfil que tienen elementos suficientes."""
    return [general_radar(job, profile), *(data for radar in profile.radars
                                           if (data := topic_radar(job, radar)) is not None)]


# --- proponer radares desde el perfil ---------------------------------------------------------------------
_CLOUD = "aws|amazon|azure|gcp|google cloud|cloud|terraform|kubernetes|k8s|docker|helm|serverless|lambda|openshift|ansible"
_LANGUAGES = r"python|java\b|javascript|typescript|bash|powershell|\bc#|\bc\+\+|\bgo\b|golang|php|ruby|rust|kotlin|scala|\bsql\b|node"
_DATA = "snowflake|databricks|etl|spark|kafka|airflow|dbt|postgres|mysql|mongo|oracle|power bi|tableau|big data|data|bigquery"
_METHODS = "scrum|agile|agil|kanban|jira|git|ci/cd|jenkins|github actions|gitlab|devops|sre|itil|prometheus|grafana|monitor"
_SYSTEMS = "linux|windows|redes|network|firewall|vpn|dns|seguridad|security|unix|vmware"


def _topics() -> tuple[tuple[str, str], ...]:
    return ((_("Cloud"), _CLOUD), (_("Lenguajes"), _LANGUAGES), (_("Datos"), _DATA),
            (_("Metodologías y herramientas"), _METHODS), (_("Sistemas y redes"), _SYSTEMS))


def suggest_radars(profile: Profile) -> list[SkillRadar]:
    """Agrupa las habilidades técnicas del perfil por temas y las blandas aparte. Los imprescindibles empiezan en 7 y los
    deseables en 5; solo salen los radares con elementos suficientes. Es una propuesta que luego se edita."""
    topics: dict[str, list[RadarAxis]] = {}
    leftovers: list[RadarAxis] = []
    for specs, level in ((profile.must, 7), (profile.nice, 5)):
        for spec in specs:
            names = " ".join(parse_term(spec)[1])
            if not names.strip():
                continue
            haystack = normalize(names)
            title = next((name for name, pattern in _topics() if re.search(pattern, haystack)), "")
            (topics.setdefault(title, []) if title else leftovers).append(RadarAxis(spec, level))
    radars = [SkillRadar(name, axes[:MAX_AXES]) for name, axes in topics.items() if len(axes) >= MIN_AXES]
    for axes in topics.values():   # los temas con pocos elementos no se pierden: se juntan en «Otras»
        if len(axes) < MIN_AXES:
            leftovers.extend(axes)
    if len(leftovers) >= MIN_AXES:
        radars.append(SkillRadar(_("Otras habilidades"), leftovers[:MAX_AXES]))
    soft = [RadarAxis(spec, level) for specs, level in ((profile.soft_must, 7), (profile.soft_nice, 5))
            for spec in specs if parse_term(spec)[0]]
    if len(soft) >= MIN_AXES:
        radars.append(SkillRadar(_("Blandas"), soft[:MAX_AXES]))
    return radars
