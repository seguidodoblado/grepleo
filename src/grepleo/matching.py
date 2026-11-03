"""Evaluación de una oferta frente a un perfil: qué criterios cumple, cuáles no y cuáles no se pueden saber.

Todo con reglas locales y sin red: los campos estructurados de la fuente (salario, modalidad, ubicación) y
la búsqueda de palabras clave y sinónimos en el texto. Una ficha resumida (sin descripción completa) no puede
demostrar que algo «no aparece»: ese criterio queda como «no se sabe» y no cuenta ni a favor ni en contra.
"""
from __future__ import annotations

from .i18n import _
from .models import CriterionResult, Evaluation, Fit, Job, Status, WorkMode
from .profiles import STUDIES_RANK, Profile, parse_term
from .textutil import (
    language_requirements,
    level_rank,
    mentions,
    normalize,
    required_years,
    studies_rank,
)

W_MUST, W_NICE, W_AVOID = 3, 1, 2
W_EXPERIENCE, W_SALARY, W_WORK_MODE, W_LOCATION, W_STUDIES, W_LANGUAGE = 2, 2, 2, 2, 1, 2

HIGH_SCORE = 0.75
MEDIUM_SCORE = 0.45


def _money(value: float) -> str:
    return f"{value:,.0f} €".replace(",", ".")


def _skill_criteria(job: Job, text: str, profile: Profile) -> list[CriterionResult]:
    results: list[CriterionResult] = []
    groups = ((profile.must, W_MUST, True), (profile.nice, W_NICE, False))
    for specs, weight, required in groups:
        for spec in specs:
            name, names = parse_term(spec)
            if not name:
                continue
            if mentions(text, names):
                results.append(CriterionResult(name, Status.MET, _("Aparece en la oferta"), weight, required))
            elif job.full_description:
                results.append(CriterionResult(name, Status.MISSING, _("No aparece en la oferta"), weight, required))
            else:
                results.append(CriterionResult(name, Status.UNKNOWN, _("Ficha resumida: no se puede saber"),
                                               weight, required))
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


def _experience_criterion(job: Job, profile: Profile) -> CriterionResult:
    name = _("Experiencia")
    needed = required_years(job.experience_text) if job.experience_text else None
    if needed is None:
        needed = required_years(job.text)
    if needed is None:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no dice cuánta experiencia pide"), W_EXPERIENCE)
    detail = _("Pide {needed}, tienes {have}").format(needed=_years(needed), have=_years(profile.years))
    status = Status.MET if profile.years >= needed else Status.MISSING
    return CriterionResult(name, status, detail, W_EXPERIENCE)


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
    if needed is None:
        return CriterionResult(name, Status.UNKNOWN, _("La oferta no pide estudios concretos"), W_STUDIES)
    have = STUDIES_RANK[profile.studies]
    return CriterionResult(name, Status.MET if have >= needed else Status.MISSING, job.studies_text, W_STUDIES)


def _language_criteria(job: Job, profile: Profile) -> list[CriterionResult]:
    results: list[CriterionResult] = []
    mine = {normalize(language): level for language, level in profile.languages.items()}
    for language, needed in language_requirements(job.text).items():
        label = f"{language} {needed}".strip()
        key = normalize(language)
        if key not in mine:
            results.append(CriterionResult(label, Status.MISSING, _("No lo tienes en tu perfil"), W_LANGUAGE))
        elif needed and mine[key] and level_rank(mine[key]) < level_rank(needed):
            results.append(CriterionResult(label, Status.MISSING,
                                           _("Pide {needed}, tienes {have}").format(needed=needed, have=mine[key]),
                                           W_LANGUAGE))
        else:
            results.append(CriterionResult(label, Status.MET, _("Cumples el nivel"), W_LANGUAGE))
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
    """Encaje y puntuación (0 a 1) sobre los criterios decididos; los «no se sabe» no cuentan."""
    decided = [item for item in criteria if item.status is not Status.UNKNOWN]
    total = sum(item.weight for item in decided)
    if not decided or total == 0:
        return Fit.UNKNOWN, None
    score = sum(item.weight for item in decided if item.status is Status.MET) / total
    required_missing = any(item.required and item.status is Status.MISSING for item in decided)
    if score >= HIGH_SCORE and not required_missing:
        return Fit.HIGH, score
    if score >= MEDIUM_SCORE or (score >= HIGH_SCORE and required_missing):
        return Fit.MEDIUM, score
    return Fit.LOW, score


def evaluate(job: Job, profile: Profile) -> Evaluation:
    text = normalize(job.text)
    criteria = _skill_criteria(job, text, profile)
    criteria.append(_experience_criterion(job, profile))
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
