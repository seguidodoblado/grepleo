"""Qué te falta más veces: lo que piden tus ofertas y no cubres, ordenado por cuántas de las que te interesan lo piden.

Usa **la misma cuenta que el encaje** (`matching.skill_credit`): algo está cubierto del todo si lo tienes con nivel
suficiente, si tienes la plataforma de la que forma parte (AWS para EC2) o si lo cubre un término genérico («IaC» con
Terraform); a medias si tu nivel es menor o tienes algo parecido; y es un hueco completo si no tienes nada. Un hueco es
cada oferta, con descripción completa, que lo pide y no lo cubres del todo; las que lo piden como requisito van aparte.
Las ofertas «que te interesan» son las de encaje alto o medio.

El cuadro contrario, `find_strengths`, reúne tus puntos fuertes: lo que ya tienes (ejes de radar con nivel de 7 o más y
tus habilidades técnicas, con el nivel con el que cuentan en el encaje) ordenado por cuántas de esas ofertas lo piden.
Sin GTK ni red.
"""
from __future__ import annotations

from dataclasses import dataclass

from .matching import asked_specs, my_skills, skill_credit
from .models import Evaluation, Fit, Job
from .profiles import Profile, parse_term
from .radar import DEMAND_NICE, DEMAND_REQUIRED, term_demand
from .similar import aliases as _aliases
from .textutil import mentions, normalize

LOW_LEVEL = DEMAND_NICE   # por debajo de esto, lo que pide una oferta como deseable ya supera tu nivel


@dataclass
class Gap:
    name: str
    how: str               # cómo lo cubres hoy, con palabras: «no la tienes», «tienes algo parecido: AWS», «tu nivel: 2 de 10»…
    credit: float          # cuánto lo cubres (0 a 1) cuando lo pide como requisito
    offers: int            # ofertas con descripción completa que lo piden y no lo cubres del todo
    required: int          # de ellas, las que lo piden como requisito o en el título
    relevant: int          # de ellas, las de encaje alto o medio

    @property
    def missing(self) -> bool:
        return self.credit == 0


def find_gaps(jobs: list[Job], evaluations: dict[str, Evaluation], profile: Profile, limit: int = 12) -> list[Gap]:
    """Los huecos de tu perfil más repetidos en las ofertas (de más a menos importantes)."""
    detailed = [job for job in jobs if job.full_description]
    if not detailed:
        return []
    texts = [normalize(job.text) for job in detailed]
    skills = my_skills(profile)
    gaps = []
    for spec in asked_specs(profile):
        names = parse_term(spec)[1]
        offers = required = relevant = 0
        for job, text in zip(detailed, texts, strict=True):
            if not mentions(text, names):
                continue   # lo barato primero: solo se calcula cuánto pide la oferta si el término aparece
            demand = term_demand(job, spec)
            if not demand or skill_credit(spec, demand, skills)[0] >= 1.0:
                continue
            offers += 1
            required += demand >= DEMAND_REQUIRED
            evaluation = evaluations.get(job.key)
            relevant += bool(evaluation and evaluation.fit in (Fit.HIGH, Fit.MEDIUM))
        if offers:
            credit, how = skill_credit(spec, DEMAND_REQUIRED, skills)
            gaps.append(Gap(parse_term(spec)[0], how, credit, offers, required, relevant))
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
    skills = my_skills(profile)
    strengths = []
    for name, spec, _level in candidates:
        counted = _count(detailed, texts, evaluations, spec, 0)
        if counted[0]:   # el nivel con el que cuenta en el encaje: el de su radar o tu nivel técnico general
            mine = _level_of(spec, skills)
            strengths.append(Strength(name, None if mine is None else round(mine), *counted))
    strengths.sort(key=lambda item: (-item.relevant, -item.required, -item.offers, normalize(item.name)))
    return strengths[:limit]


def _level_of(spec: str, skills: list[tuple[frozenset[str], float, str]]) -> float | None:
    """El nivel con el que cuenta lo que tienes: el de su radar o tu nivel técnico general; un par como «CI/CD» tiene el
    menor de sus dos mitades."""
    names = _aliases(spec)
    direct = next((level for have, level, _name in skills if have & names), None)
    if direct is not None:
        return direct
    for name in names:
        parts = [part.strip() for part in name.split("/")]
        levels = [next((level for have, level, _n in skills if part in have), None) for part in parts]
        if len(parts) > 1 and all(level is not None for level in levels):
            return min(levels)
    return None


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
