"""Qué te falta más veces: lo que piden tus ofertas y no cubres, ordenado por cuántas de las que te interesan lo piden.

Hay dos clases de hueco, siempre sobre ofertas con descripción completa (en una ficha resumida lo que «no aparece» no
quiere decir que no se pida):

- **No está en tu perfil**: algo del catálogo de requisitos habituales que ninguna de tus listas ni radares nombra.
- **Nivel bajo**: un eje de tus radares con un nivel menor de 7, que es lo que una oferta pide como deseable, de modo
  que las ofertas que lo piden más alto lo piden por encima de lo que tienes.

Las ofertas «que te interesan» son las de encaje alto o medio. El cuadro contrario, `find_strengths`, reúne tus puntos
fuertes: lo que ya tienes (ejes de radar con nivel de 7 o más y tus habilidades técnicas) ordenado por cuántas de esas
ofertas lo piden. Sin GTK ni red.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Evaluation, Fit, Job
from .panorama import DEFAULT_CATALOG
from .profiles import Profile, parse_term
from .radar import DEMAND_NICE, DEMAND_REQUIRED, term_demand
from .textutil import mentions, normalize

LOW_LEVEL = DEMAND_NICE   # por debajo de esto, lo que pide una oferta como deseable ya supera tu nivel


@dataclass
class Gap:
    name: str
    level: int | None      # tu nivel (0 a 10) si el elemento está en un radar; None si no está en tu perfil
    offers: int            # ofertas con descripción completa que lo piden por encima de tu nivel
    required: int          # de ellas, las que lo piden como requisito o en el título
    relevant: int          # de ellas, las de encaje alto o medio

    @property
    def missing(self) -> bool:
        return self.level is None


def _aliases(spec: str) -> set[str]:
    return {normalize(name) for name in parse_term(spec)[1]}


def _is_covered(aliases: set[str], covered: set[str]) -> bool:
    """Lo nombra algo de tu perfil, o es un par como «CI/CD» cuyas dos mitades ya tienes por separado."""
    if aliases & covered:
        return True
    return any("/" in alias and all(part.strip() in covered for part in alias.split("/")) for alias in aliases)


def find_gaps(jobs: list[Job], evaluations: dict[str, Evaluation], profile: Profile, limit: int = 12) -> list[Gap]:
    """Los huecos de tu perfil más repetidos en las ofertas (de más a menos importantes)."""
    detailed = [job for job in jobs if job.full_description]
    if not detailed:
        return []
    covered = set().union(*(_aliases(spec) for spec in (*profile.all_must, *profile.all_nice)), set())
    covered |= {normalize(radar.name) for radar in profile.radars}   # «Cloud» ya lo cubren sus ejes
    languages = {normalize(name) for name in profile.languages}
    levels: dict[str, tuple[str, set[str], int]] = {}   # nombre normalizado -> (nombre, sinónimos, nivel)
    for radar in profile.radars:
        for axis in radar.axes:
            name = parse_term(axis.spec)[0]
            if name:
                known = levels.get(normalize(name))
                level = max(axis.level, known[2]) if known else axis.level
                levels[normalize(name)] = (name, _aliases(axis.spec), level)
    candidates: list[tuple[str, str, int | None]] = []   # (nombre, especificación, nivel)
    seen: set[str] = set()
    for name, aliases, level in levels.values():
        if level < LOW_LEVEL:
            spec = next(spec for radar in profile.radars for axis in radar.axes
                        for spec in (axis.spec,) if normalize(parse_term(spec)[0]) == normalize(name))
            candidates.append((name, spec, level))
        seen |= aliases
    for spec in DEFAULT_CATALOG:
        aliases = _aliases(spec)
        if aliases & seen or aliases & languages or _is_covered(aliases, covered):
            continue
        seen |= aliases
        candidates.append((parse_term(spec)[0], spec, None))
    texts = [normalize(job.text) for job in detailed]
    gaps = []
    for name, spec, level in candidates:
        counted = _count(detailed, texts, evaluations, spec, level if level is not None else 0)
        if counted[0]:
            gaps.append(Gap(name, level, *counted))
    gaps.sort(key=lambda gap: (-gap.relevant, -gap.required, -gap.offers, normalize(gap.name)))
    return gaps[:limit]


@dataclass
class Strength:
    name: str
    level: int | None      # tu nivel (0 a 10) si el elemento está en un radar; None si solo está en tus habilidades
    offers: int            # ofertas con descripción completa que lo citan
    required: int          # de ellas, las que lo piden como requisito o en el título
    relevant: int          # de ellas, las de encaje alto o medio


def _count(detailed: list[Job], texts: list[str], evaluations: dict[str, Evaluation], spec: str,
           floor: float) -> tuple[int, int, int]:
    """(ofertas, como requisito, de encaje alto o medio) entre las que piden `spec` por encima de `floor`."""
    offers = required = relevant = 0
    names = parse_term(spec)[1]
    for job, text in zip(detailed, texts, strict=True):
        if not mentions(text, names):
            continue   # lo barato primero: solo se calcula cuánto pide la oferta si el término aparece
        demand = term_demand(job, spec)
        if not demand or demand <= floor:
            continue
        offers += 1
        required += demand >= DEMAND_REQUIRED
        evaluation = evaluations.get(job.key)
        relevant += bool(evaluation and evaluation.fit in (Fit.HIGH, Fit.MEDIUM))
    return offers, required, relevant


def find_strengths(jobs: list[Job], evaluations: dict[str, Evaluation], profile: Profile,
                   limit: int = 8) -> list[Strength]:
    """Lo que ya tienes y más piden tus ofertas: ejes de radar con nivel de 7 o más y tus habilidades técnicas."""
    detailed = [job for job in jobs if job.full_description]
    if not detailed:
        return []
    texts = [normalize(job.text) for job in detailed]
    candidates: list[tuple[str, str, int | None]] = []
    seen: set[str] = set()
    for radar in profile.radars:
        for axis in radar.axes:
            name = parse_term(axis.spec)[0]
            aliases = _aliases(axis.spec)
            if name and axis.level >= LOW_LEVEL and not aliases & seen:
                candidates.append((name, axis.spec, axis.level))
                seen |= aliases
    for spec in _joined_pairs((*profile.must, *profile.nice)):
        name, aliases = parse_term(spec)[0], _aliases(spec)
        if name and not aliases & seen and not _radar_has(profile, aliases):
            candidates.append((name, spec, None))
            seen |= aliases
    strengths = []
    for name, spec, level in candidates:
        counted = _count(detailed, texts, evaluations, spec, 0)
        if counted[0]:
            strengths.append(Strength(name, level, *counted))
    strengths.sort(key=lambda item: (-item.relevant, -item.required, -item.offers, normalize(item.name)))
    return strengths[:limit]


def _joined_pairs(specs: tuple[str, ...]) -> list[str]:
    """«CI» y «CD» por separado son «CI/CD» para las ofertas: se cuentan juntos, no dos veces lo mismo."""
    names = {normalize(parse_term(spec)[0]) for spec in specs}
    if {"ci", "cd"} <= names:
        rest = [spec for spec in specs if normalize(parse_term(spec)[0]) not in ("ci", "cd")]
        return [*rest, "CI/CD|ci cd|integración continua"]
    return list(specs)


def _radar_has(profile: Profile, aliases: set[str]) -> bool:
    """¿Algún eje de tus radares nombra esto con un nivel bajo? Entonces es un hueco, no un punto fuerte."""
    return any(aliases & _aliases(axis.spec) for radar in profile.radars for axis in radar.axes)
