"""Lo que tienes y lo que se busca: tus habilidades con su nivel, y cuánto cubren lo que pide una oferta.

Es la cuenta que comparten el encaje, los huecos y los puntos fuertes y los radares. Una habilidad pedida está cubierta
del todo si la tienes con nivel suficiente, si tienes la plataforma de la que forma parte (AWS para EC2) o si la cubre un
término genérico («IaC» con Terraform); a medias si tu nivel es menor o tienes algo parecido; y no está cubierta si no
tienes nada. Sin GTK ni red.
"""
from __future__ import annotations

from .i18n import _
from .panorama import DEFAULT_CATALOG
from .profiles import Profile, parse_term
from .similar import PARENT_FACTOR, SIMILAR_FACTOR, aliases, parents_of, similar_to, umbrella_members

FULL_CREDIT = 0.8      # con este nivel frente a lo que se pide se da por cubierto del todo
SOFT_DEMAND = 7.0      # lo que se supone que pide una oferta de una habilidad blanda: con 6 de 10 o más, cubierta

_LANGUAGE_TERMS = frozenset({"ingles", "english"})   # los idiomas se evalúan aparte, con su nivel

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


Skill = tuple[frozenset[str], float, str]   # (todo lo que la nombra, tu nivel de 0 a 10, su nombre)


def my_skills(profile: Profile) -> list[Skill]:
    """Tus habilidades técnicas con su nivel: los ejes de tus radares y las de tus listas. Va por orden de precisión: si
    algo está en un radar con tema, manda el nivel de ese eje."""
    skills = [(aliases(axis.spec), float(axis.level), parse_term(axis.spec)[0]) for radar in profile.radars
              for axis in radar.axes]
    skills += [(aliases(spec), float(level), parse_term(spec)[0]) for spec, level in profile.technical_levels()]
    return [skill for skill in skills if skill[0]]


def my_soft(profile: Profile) -> list[Skill]:
    """Tus habilidades blandas con su nivel."""
    return [(aliases(spec), float(level), parse_term(spec)[0]) for spec, level in profile.soft_levels()
            if aliases(spec)]


def asked_specs(profile: Profile) -> list[str]:
    """Lo que se busca en una oferta: lo que aparece en tu perfil y tus radares (con tus sinónimos) y el catálogo de
    requisitos habituales (cada elemento una vez)."""
    specs, seen = [], set()
    candidates = [*(spec for spec, _level in profile.technical_levels()),   # primero las tuyas, con tus sinónimos
                  *(axis.spec for radar in profile.radars for axis in radar.axes), *DEFAULT_CATALOG]
    for spec in candidates:
        names = aliases(spec)
        if names and not names & seen and not names & _LANGUAGE_TERMS:
            specs.append(spec)
            seen |= names
    return specs


def asked_soft_specs(profile: Profile) -> list[str]:
    """Las habilidades blandas que se buscan en una oferta: el vocabulario habitual más las de tu perfil."""
    specs, seen = [], set()
    for spec in (*(spec for spec, _level in profile.soft_levels()), *SOFT_VOCABULARY):
        names = aliases(spec)
        if names and not names & seen:
            specs.append(spec)
            seen |= names
    return specs


def skill_credit(spec: str, demand: float, skills: list[Skill]) -> tuple[float, str]:
    """(crédito de 0 a 1, cómo lo cubres dicho con palabras) de una habilidad pedida."""
    names = aliases(spec)
    mine = next((level for have, level, _name in skills if have & names), None)
    if mine is None:   # un término genérico como «Cloud» lo cubre cualquiera de sus concreciones
        mine = max((level for have, level, _name in skills if any(have & other for other in umbrella_members(names))),
                   default=None)
    if mine is None:   # un par como «CI/CD» lo cubres si tienes «CI» y «CD» por separado
        for name in names:
            parts = [part.strip() for part in name.split("/")]
            levels = [next((level for have, level, _name in skills if part in have), None) for part in parts]
            if len(parts) > 1 and all(level is not None for level in levels):
                mine = min(levels)
                break
    if mine is not None:
        credit = min(mine, demand) / demand
        if credit >= FULL_CREDIT:
            return 1.0, _("la tienes")
        return credit, _("tu nivel: {level} de 10").format(level=f"{mine:.0f}")
    base = max(((level, name) for have, level, name in skills if any(have & parent for parent in parents_of(names))),
               key=lambda item: item[0], default=None)
    if base is not None:   # tienes la plataforma o la base de lo que se pide (AWS para EC2)
        credit = PARENT_FACTOR * min(base[0], demand) / demand
        text = _("tienes la base: {name}").format(name=base[1])
        return (1.0 if credit >= FULL_CREDIT else credit), text
    related = similar_to(names)
    best = max(((level, name) for have, level, name in skills if any(have & other for other in related)),
               key=lambda item: item[0], default=None)
    if best is not None:
        credit = SIMILAR_FACTOR * min(best[0], demand) / demand
        return credit, _("tienes algo parecido: {name}").format(name=best[1])
    return 0.0, _("no la tienes")


def soft_credit(spec: str, skills: list[Skill]) -> tuple[float, str]:
    """(crédito, cómo la cubres) de una habilidad blanda pedida: tu nivel frente a `SOFT_DEMAND`."""
    names = aliases(spec)
    mine = next((level for have, level, _name in skills if have & names), None)
    if mine is None:
        return 0.0, _("no la tienes")
    credit = min(mine, SOFT_DEMAND) / SOFT_DEMAND
    if credit >= FULL_CREDIT:
        return 1.0, _("la tienes")
    return credit, _("tu nivel: {level} de 10").format(level=f"{mine:.0f}")
