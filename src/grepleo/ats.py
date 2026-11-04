"""Estimación de si un CV pasaría el filtro automático (ATS) de una oferta. Sin GTK.

No existe un «porcentaje de éxito ATS» publicado: cada empresa configura su sistema. Esto es una **estimación local y
explicable** con lo que esos filtros suelen mirar: las palabras clave de la oferta que aparecen en tu CV, el cargo, la
estructura del CV y los requisitos eliminatorios (experiencia, estudios, idiomas).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .cv import profile_markdown, uploaded_cv_text
from .i18n import _
from .matching import experience_requirement, knockout_criteria
from .models import Job, Status
from .panorama import DEFAULT_CATALOG
from .profiles import Profile, parse_term
from .radar import SOFT_VOCABULARY, term_demand
from .textutil import mentions, normalize

W_KEYWORDS, W_TITLE, W_FORMAT = 0.60, 0.15, 0.25
KNOCKOUT_FACTOR = 0.6          # cada requisito eliminatorio que no cumples (estudios, idiomas) multiplica el resultado por esto
# La experiencia pesa según lo que te falta: 1 año más de lo que tienes casi no se nota (las ofertas de «2 años» suelen
# aceptar 1), y a partir de 3 años de diferencia el filtro suele descartar de verdad.
EXPERIENCE_FACTORS = ((1, 0.85), (2, 0.7))   # (años que faltan como máximo, factor); más: KNOCKOUT_FACTOR
LIKELY, POSSIBLE = 70, 45      # a partir de estos porcentajes: «probable» y «posible»
_STOPWORDS = frozenset(["de", "del", "la", "las", "el", "los", "y", "e", "o", "u", "en", "con", "para", "por", "un", "una", "al", "sr", "jr", "senior", "junior", "lead", "ref", "remoto", "hibrido", "presencial"])


@dataclass
class AtsEstimate:
    percent: int
    reliability: str                                  # «high», «medium» o «low»
    keyword_score: float | None                       # 0–1; None si la oferta no permite saberlo
    title_score: float | None
    format_score: float
    found: list[str] = field(default_factory=list)    # palabras clave de la oferta que tu CV cita
    missing: list[str] = field(default_factory=list)  # las que no cita, de más a menos importantes
    failed: list[str] = field(default_factory=list)   # requisitos eliminatorios que no cumples
    factors: list[float] = field(default_factory=list)   # lo que resta cada uno (el factor por el que se multiplica)
    unknown: int = 0                                  # requisitos eliminatorios que no se pueden saber
    from_upload: bool = False                         # se ha leído también el CV subido
    no_keywords: bool = False                         # la oferta no cita ninguna palabra clave conocida: el resultado se limita

    @property
    def verdict(self) -> str:
        if self.percent >= LIKELY:
            return _("Es probable que pase el filtro")
        if self.percent >= POSSIBLE:
            return _("Puede pasar, según lo estricto que sea el filtro")
        return _("Es poco probable que pase el filtro")

    @property
    def reliability_label(self) -> str:
        return {"high": _("alta"), "medium": _("media"), "low": _("baja")}[self.reliability]


def _technical_terms(profile: Profile) -> list[str]:
    catalog = [spec for spec in DEFAULT_CATALOG if normalize(parse_term(spec)[0]) != "ingles"]   # el inglés es un idioma
    return [*catalog, *profile.must, *profile.nice]


def _soft_terms(profile: Profile) -> list[str]:
    return [*SOFT_VOCABULARY, *profile.soft_must, *profile.soft_nice]


def _terms(profile: Profile) -> list[str]:
    return [*_technical_terms(profile), *_soft_terms(profile)]


def _stem(word: str) -> str:
    """Una raíz tosca para comparar «ingeniero», «ingeniera» e «ingenieros»: sin plural ni terminación de género."""
    if len(word) > 4:
        word = word.removesuffix("s")
    return word[:-1] if len(word) > 4 and word[-1] in "aoe" else word


def _title_tokens(title: str) -> list[str]:
    words = re.findall(r"[a-z0-9+#]+", normalize(title))
    return list(dict.fromkeys(_stem(word) for word in words if len(word) >= 3 and not word.isdigit()
                              and word not in _STOPWORDS))


def _format_score(profile: Profile) -> float:
    """Cuántas secciones estándar tiene el CV con contenido; la experiencia pesa el doble, porque es lo primero que lee."""
    has = ((bool(profile.headline.strip()) or profile.years > 0), bool(profile.experience.strip()),
           (bool(profile.studies) or bool(profile.education.strip())), bool(profile.languages),
           bool(profile.all_must or profile.all_nice))
    return (has[0] + 2 * has[1] + has[2] + has[3] + has[4]) / 6


def experience_factor(shortfall: int) -> float:
    """El factor de una experiencia que no llega: según los años que faltan."""
    for years, factor in EXPERIENCE_FACTORS:
        if shortfall <= years:
            return factor
    return KNOCKOUT_FACTOR


def estimate_ats(job: Job, profile: Profile) -> AtsEstimate:
    """La estimación para una oferta y un perfil."""
    upload = uploaded_cv_text(profile)
    cv = normalize(profile_markdown(profile) + "\n" + upload)

    # 1) palabras clave de la oferta que tu CV cita, ponderadas por cuánto las pide la oferta (10, 7 o 5)
    weights: dict[str, float] = {}
    present: dict[str, bool] = {}
    technical = 0   # cuántas de las palabras clave reconocidas son técnicas (las blandas las cita cualquier oferta)
    soft = {normalize(parse_term(spec)[0]) for spec in _soft_terms(profile)}
    for spec in _terms(profile):
        name, names = parse_term(spec)
        weight = term_demand(job, spec) if name and job.full_description else None   # una ficha resumida no da palabras clave
        if not weight or normalize(name) in weights:
            continue
        weights[normalize(name)] = weight
        present[normalize(name)] = mentions(cv, names)
        technical += normalize(name) not in soft
    total = sum(weights.values())
    keywords = sum(weights[key] for key, ok in present.items() if ok) / total if total else None
    ordered = sorted(weights, key=lambda key: -weights[key])
    names_by_key = {normalize(parse_term(spec)[0]): parse_term(spec)[0] for spec in _terms(profile)}
    found = [names_by_key[key] for key in ordered if present[key]]
    missing = [names_by_key[key] for key in ordered if not present[key]]

    # 2) el cargo: cuántas palabras del título de la oferta aparecen en tu CV
    tokens = _title_tokens(job.title)
    words = {_stem(word) for word in re.findall(r"[a-z0-9+#]+", cv)}
    title = sum(1 for token in tokens if token in words) / len(tokens) if tokens else None

    # 3) la estructura del CV
    structure = _format_score(profile)

    parts = [(W_KEYWORDS, keywords), (W_TITLE, title), (W_FORMAT, structure)]
    available = [(weight, score) for weight, score in parts if score is not None]
    base = sum(weight * score for weight, score in available) / sum(weight for weight, _score in available)

    # 4) requisitos eliminatorios
    criteria = knockout_criteria(job, profile)
    failed, factors = [], []
    needed = experience_requirement(job)
    for index, item in enumerate(criteria):   # el primero es siempre la experiencia
        if item.status is not Status.MISSING:
            continue
        failed.append(item.name)
        factors.append(experience_factor(needed - profile.years) if index == 0 and needed is not None
                       else KNOCKOUT_FACTOR)
    unknown = sum(1 for item in criteria if item.status is Status.UNKNOWN)
    penalty = 1.0
    for factor in factors:
        penalty *= factor
    percent = round(100 * base * penalty)

    reliability = "low"
    if job.full_description:
        reliability = "high" if len(weights) >= 4 else "medium"
    # Una oferta completa que no cita ninguna palabra clave técnica conocida (las blandas no cuentan: «trabajo en equipo» sale
    # en cualquier oferta) no es de tu campo, o usa un vocabulario que el catálogo no tiene: un ATS real tendría sus propias palabras clave (que tu CV, probablemente, no cita). Sin esto, la estructura
    # del CV y el título dejarían esa oferta en lo más alto de la lista, y no es cierto.
    no_keywords = job.full_description and technical == 0
    if no_keywords:
        reliability = "low"
        percent = min(percent, POSSIBLE - 1)
    return AtsEstimate(max(0, min(100, percent)), reliability, keywords, title, structure, found, missing, failed,
                       factors, unknown, bool(upload), no_keywords)
