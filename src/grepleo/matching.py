"""Evaluación de una oferta frente a un perfil: qué criterios cumple, cuáles no y cuáles no se pueden saber.

Todo con reglas locales y sin red: los campos estructurados de la fuente (salario, modalidad, ubicación) y
la búsqueda de palabras clave y sinónimos en el texto. Una ficha resumida (sin descripción completa) no puede
demostrar que algo «no aparece»: ese criterio queda como «no se sabe» y no cuenta ni a favor ni en contra.
"""
from __future__ import annotations

import re

from .i18n import _
from .models import CriterionResult, Evaluation, Fit, Job, Status, WorkMode
from .panorama import DEFAULT_CATALOG
from .profiles import STUDIES_RANK, Profile, parse_term
from .radar import DEMAND_NICE, DEMAND_REQUIRED, SCALE, SOFT_VOCABULARY, demand_note, term_demand
from .similar import PARENT_FACTOR, SIMILAR_FACTOR, aliases, parents_of, similar_to, umbrella_members
from .textutil import (
    language_requirements,
    level_rank,
    mentions,
    normalize,
    required_years,
    studies_in_description,
    studies_rank,
)

W_REQUIRED, W_NICE_ASK, W_MENTIONED, W_SOFT, W_AVOID = 3, 2, 1, 1, 2
W_EXPERIENCE, W_SALARY, W_WORK_MODE, W_LOCATION, W_STUDIES, W_LANGUAGE = 3, 2, 2, 2, 1, 2

SECONDARY = 0.7        # lo que conoces (secundario) cuenta con este porcentaje de tu nivel técnico general
FULL_CREDIT = 0.8      # con este nivel frente a lo que se pide se da por cubierto del todo
EVIDENCE = 6           # peso de habilidades pedidas por debajo del cual el encaje no se fía de sí mismo
HIGH_SCORE = 0.80
MEDIUM_SCORE = 0.55


def _money(value: float) -> str:
    return f"{value:,.0f} €".replace(",", ".")


_LANGUAGE_TERMS = frozenset({"ingles", "english"})   # los idiomas se evalúan aparte, con su nivel


def _weight(demand: float) -> int:
    """Lo que pesa una habilidad según cuánto la pide la oferta: requisito 3, deseable 2, solo mencionada 1."""
    return W_REQUIRED if demand >= DEMAND_REQUIRED else W_NICE_ASK if demand >= DEMAND_NICE else W_MENTIONED


def my_skills(profile: Profile) -> list[tuple[frozenset[str], float, str]]:
    """Lo que tienes y con qué nivel (0 a 10): los ejes de tus radares y tus habilidades principales, con tu nivel
    técnico general del radar general (10 si no lo has tocado), y las secundarias, con el 70 % de él. Va por orden de
    precisión: si algo está en un radar con tema, manda el nivel de ese eje."""
    general = float(profile.radar.get("technical", SCALE))   # tu nivel técnico general del radar; sin tocarlo, 10
    skills = [(aliases(axis.spec), float(axis.level), parse_term(axis.spec)[0]) for radar in profile.radars
              for axis in radar.axes]
    skills += [(aliases(spec), general, parse_term(spec)[0]) for spec in profile.must]
    skills += [(aliases(spec), general * SECONDARY, parse_term(spec)[0]) for spec in profile.nice]
    return [skill for skill in skills if skill[0]]


def asked_specs(profile: Profile) -> list[str]:
    """Lo que se busca en una oferta: el catálogo de requisitos habituales más lo que aparece en tu perfil y tus
    radares (cada elemento una vez)."""
    specs, seen = [], set()
    candidates = [*DEFAULT_CATALOG, *profile.must, *profile.nice,
                  *(axis.spec for radar in profile.radars for axis in radar.axes)]
    for spec in candidates:
        names = aliases(spec)
        if names and not names & seen and not names & _LANGUAGE_TERMS:
            specs.append(spec)
            seen |= names
    return specs


def skill_credit(spec: str, demand: float, skills: list[tuple[frozenset[str], float, str]]) -> tuple[float, str]:
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


def _skill_criteria(job: Job, text: str, profile: Profile) -> list[CriterionResult]:
    """Lo que la oferta pide y cómo lo cubres. Lo que tienes y la oferta no cita no cuenta ni a favor ni en contra:
    cada empresa pide un perfil ideal y luego cede, así que un hueco resta según lo que pese, nunca descarta."""
    skills = my_skills(profile)
    asked: list[tuple[float, CriterionResult]] = []
    for spec in asked_specs(profile):
        name, names = parse_term(spec)
        if not mentions(text, names):
            continue
        demand = term_demand(job, spec)
        if demand is None:   # ficha resumida: lo que cita es un requisito mínimo
            demand = DEMAND_REQUIRED
        if not demand:
            continue
        credit, how = skill_credit(spec, demand, skills)
        status = Status.MET if credit >= 1 else Status.PARTIAL if credit > 0 else Status.MISSING
        asked.append((demand, CriterionResult(
            name, status, f"{demand_note(demand)} · {how}", _weight(demand), demand >= DEMAND_REQUIRED, "hard",
            credit if status is Status.PARTIAL else None)))
    asked.sort(key=lambda item: (-item[0], normalize(item[1].name)))
    results = [item for _demand, item in asked]
    mine_soft = [aliases(spec) for spec in (*profile.soft_must, *profile.soft_nice)]
    for spec in (*SOFT_VOCABULARY, *profile.soft_must, *profile.soft_nice):
        name, names = parse_term(spec)
        if not name or not mentions(text, names):
            continue
        if any(item.name == name.capitalize() or normalize(item.name) == normalize(name) for item in results
               if item.group == "soft"):
            continue
        have = any(aliases(spec) & other for other in mine_soft)
        results.append(CriterionResult(name[:1].upper() + name[1:], Status.MET if have else Status.MISSING,
                                       _("la pide la oferta · la tienes") if have
                                       else _("la pide la oferta · no la tienes"), W_SOFT, False, "soft"))
    for spec in profile.avoid:
        name, names = parse_term(spec)
        if not name:
            continue
        label = _("Sin «{term}»").format(term=name)
        if mentions(text, names):
            results.append(CriterionResult(label, Status.MISSING, _("La oferta lo menciona"), W_AVOID))
        elif job.full_description:
            results.append(CriterionResult(label, Status.MET, _("No aparece en la oferta"), W_AVOID))
        else:
            results.append(CriterionResult(label, Status.UNKNOWN, _("Ficha resumida: no se puede saber"), W_AVOID))
    return results


def _years(count: int) -> str:
    return _("{count} año").format(count=count) if count == 1 else _("{count} años").format(count=count)


def experience_requirement(job: Job) -> int | None:
    """Los años de experiencia que pide la oferta (el campo del portal o, si no, su texto), o None si no lo dice."""
    needed = required_years(job.experience_text) if job.experience_text else None
    return needed if needed is not None else required_years(job.text, strict=True)


def _experience_criterion(job: Job, profile: Profile) -> CriterionResult:
    name = _("Experiencia")
    needed = experience_requirement(job)
    if needed is None:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no dice cuánta experiencia pide"), W_EXPERIENCE)
    detail = _("Pide {needed}, tienes {have}").format(needed=_years(needed), have=_years(profile.years))
    status = Status.MET if profile.years >= needed else Status.MISSING
    return CriterionResult(name, status, detail, W_EXPERIENCE)


EXPERIENCE_CREDIT = {1: 0.6, 2: 0.3}   # cuánto cubres si te faltan 1 o 2 años; con 3 o más, nada


def _experience_in_fit(job: Job, profile: Profile) -> CriterionResult:
    """La experiencia para el encaje: si te faltan uno o dos años no es un «no» tajante (las empresas ceden), pero sí
    un descuento grande; la estimación ATS sigue usando el criterio estricto (`_experience_criterion`)."""
    criterion = _experience_criterion(job, profile)
    needed = experience_requirement(job)
    if criterion.status is not Status.MISSING or needed is None:
        return criterion
    credit = EXPERIENCE_CREDIT.get(needed - profile.years)
    if credit is None:
        return criterion
    return CriterionResult(criterion.name, Status.PARTIAL, criterion.detail, criterion.weight, credit=credit)


_SENIOR = re.compile(r"(?<!\w)(senior|sr|lead|principal|staff|head of|manager|director|responsable|jefe|"
                     r"arquitect[oa]|architect)(?!\w)")
_JUNIOR = re.compile(r"(?<!\w)(junior|jr|entry[- ]level|trainee|becari[oa]|practicas|graduate)(?!\w)")
SENIOR_YEARS = 5   # los años que se suponen a un puesto «senior» cuando la oferta no dice cuántos pide


def _level_criterion(job: Job, profile: Profile) -> CriterionResult | None:
    """El nivel que dice el título («Senior», «Lead», «Junior»…) cuando la oferta no concreta los años que pide:
    sin esto, un puesto de dirección sin requisitos escritos puntuaría como uno de entrada."""
    title = normalize(job.title)
    if experience_requirement(job) is not None:
        return None
    name = _("Nivel del puesto")
    if _SENIOR.search(title):
        gap = SENIOR_YEARS - profile.years
        detail = _("El título pide un perfil sénior y tienes {have}").format(have=_years(profile.years))
        if gap <= 0:
            return CriterionResult(name, Status.MET, detail, W_EXPERIENCE)
        credit = EXPERIENCE_CREDIT.get(gap)
        if credit is None:
            return CriterionResult(name, Status.MISSING, detail, W_EXPERIENCE)
        return CriterionResult(name, Status.PARTIAL, detail, W_EXPERIENCE, credit=credit)
    if _JUNIOR.search(title):
        return CriterionResult(name, Status.MET, _("El título es de nivel junior o de entrada"), W_EXPERIENCE)
    return None


def _salary_criterion(job: Job, profile: Profile) -> CriterionResult:
    name = _("Salario")
    top = job.salary_max if job.salary_max is not None else job.salary_min
    if top is None:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no publica salario"), W_SALARY)
    estimated = _(" (estimado por el portal)") if job.salary_estimated else ""
    detail = _("Hasta {top} frente a tu mínimo de {wanted}").format(top=_money(top), wanted=_money(profile.salary_min))
    return CriterionResult(name, Status.MET if top >= profile.salary_min else Status.MISSING, detail + estimated,
                           W_SALARY)


def _work_mode_criterion(job: Job, profile: Profile) -> CriterionResult:
    name = _("Modalidad")
    if job.work_mode is WorkMode.UNKNOWN:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no dice la modalidad"), W_WORK_MODE)
    accepted = job.work_mode.value in profile.work_modes
    return CriterionResult(name, Status.MET if accepted else Status.MISSING, job.work_mode.label, W_WORK_MODE)


def _location_criterion(job: Job, profile: Profile) -> CriterionResult:
    name = _("Ubicación")
    if job.work_mode is WorkMode.REMOTE:
        return CriterionResult(name, Status.MET, _("Remoto"), W_LOCATION)
    if not job.location:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no dice la ubicación"), W_LOCATION)
    place = normalize(job.location)
    near = any(normalize(wanted) in place for wanted in profile.locations)
    return CriterionResult(name, Status.MET if near else Status.MISSING, job.location, W_LOCATION)


def _studies_criterion(job: Job, profile: Profile) -> CriterionResult:
    name = _("Estudios")
    needed = studies_rank(job.studies_text) if job.studies_text else None
    detail = job.studies_text
    if needed is None:   # sin campo del portal, se busca en la descripción completa
        needed, detail = studies_in_description(job.text) if job.full_description else (None, "")
    if needed is None:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no pide estudios concretos"), W_STUDIES)
    have = STUDIES_RANK[profile.studies]
    return CriterionResult(name, Status.MET if have >= needed else Status.MISSING, detail, W_STUDIES)


def _language_criteria(job: Job, profile: Profile) -> list[CriterionResult]:
    results: list[CriterionResult] = []
    mine = {normalize(language): level for language, level in profile.languages.items()}
    for language, needed in language_requirements(job.text).items():
        label = f"{language} {needed}".strip()
        key = normalize(language)
        if key not in mine:
            results.append(CriterionResult(label, Status.MISSING, _("No lo tienes en tu perfil"), W_LANGUAGE,
                                           group="hard"))
        elif needed and mine[key] and level_rank(mine[key]) < level_rank(needed):
            results.append(CriterionResult(label, Status.MISSING,
                                           _("Pide {needed}, tienes {have}").format(needed=needed, have=mine[key]),
                                           W_LANGUAGE, group="hard"))
        else:
            results.append(CriterionResult(label, Status.MET, _("Cumples el nivel"), W_LANGUAGE, group="hard"))
    return results


def categorize(job: Job, profile: Profile) -> str:
    """El primer tipo del perfil que cite el título; si ninguno, el primero que cite el texto; si no, «»."""
    title = normalize(job.title)
    for category in profile.categories:
        if mentions(title, category.keywords):
            return category.name
    text = normalize(job.text)
    for category in profile.categories:
        if mentions(text, category.keywords):
            return category.name
    return ""


def fit_from(criteria: list[CriterionResult]) -> tuple[Fit, float | None]:
    """Encaje y puntuación (0 a 1) sobre los criterios decididos; los «no se sabe» no cuentan.

    Cada criterio aporta su peso por lo que cubres (todo, nada o una parte). Un hueco, aunque sea de un requisito,
    resta según lo que pese pero no fija el encaje: las empresas ceden, y así el orden refleja las posibilidades."""
    decided = [item for item in criteria if item.status is not Status.UNKNOWN]
    total = sum(item.weight for item in decided)
    if not decided or total == 0:
        return Fit.UNKNOWN, None
    # con poco pedido en habilidades (una oferta que casi no concreta qué quiere), las condiciones sueltas no pueden dar
    # un encaje alto: lo que falta de evidencia cuenta como no cubierto
    evidence = sum(item.weight for item in decided if item.group in ("hard", "soft"))
    total += max(0, EVIDENCE - evidence)
    score = sum(item.weight * item.value for item in decided) / total
    if score >= HIGH_SCORE:
        return Fit.HIGH, score
    return (Fit.MEDIUM if score >= MEDIUM_SCORE else Fit.LOW), score


def knockout_criteria(job: Job, profile: Profile) -> list[CriterionResult]:
    """Lo que un filtro automático suele usar para descartar: la experiencia que pide, los estudios (si indicas los
    tuyos) y los idiomas. Sirve a la estimación ATS."""
    criteria = [_experience_criterion(job, profile)]
    if profile.studies:
        criteria.append(_studies_criterion(job, profile))
    criteria.extend(_language_criteria(job, profile))
    return criteria


def evaluate(job: Job, profile: Profile) -> Evaluation:
    text = normalize(job.text)
    criteria = _skill_criteria(job, text, profile)
    criteria.append(_experience_in_fit(job, profile))
    level = _level_criterion(job, profile)
    if level is not None:
        criteria.append(level)
    if profile.salary_min > 0:
        criteria.append(_salary_criterion(job, profile))
    if profile.work_modes:
        criteria.append(_work_mode_criterion(job, profile))
    if profile.locations:
        criteria.append(_location_criterion(job, profile))
    if profile.studies:
        criteria.append(_studies_criterion(job, profile))
    criteria.extend(_language_criteria(job, profile))
    fit, score = fit_from(criteria)
    return Evaluation(fit, score, criteria, categorize(job, profile))
