"""Modelos de datos sin GTK: ofertas, criterios evaluados y estados."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .i18n import _


class WorkMode(Enum):
    """Modalidad de trabajo. Los valores son claves estables: lo que se muestra es `label`."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {WorkMode.REMOTE: _("Remoto"), WorkMode.HYBRID: _("Híbrido"),
                WorkMode.ONSITE: _("Presencial"), WorkMode.UNKNOWN: "—"}[self]


class Fit(Enum):
    """Encaje de una oferta con el perfil. El orden de `rank` sirve para ordenar."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {Fit.HIGH: _("Alto"), Fit.MEDIUM: _("Medio"), Fit.LOW: _("Bajo"),
                Fit.UNKNOWN: _("Sin datos")}[self]

    @property
    def rank(self) -> int:
        return {Fit.HIGH: 3, Fit.MEDIUM: 2, Fit.LOW: 1, Fit.UNKNOWN: 0}[self]


class Status(Enum):
    """Resultado de un criterio frente a una oferta."""
    MET = "met"          # ✓ cumple
    MISSING = "missing"  # ✗ no cumple, o no aparece en una descripción completa
    UNKNOWN = "unknown"  # ? la oferta no da el dato (ficha resumida)

    @property
    def symbol(self) -> str:
        return {Status.MET: "✓", Status.MISSING: "✗", Status.UNKNOWN: "?"}[self]


class JobState(Enum):
    """Estado que le pone el usuario a una oferta."""
    NEW = "new"
    FAVORITE = "favorite"
    APPLIED = "applied"
    DISCARDED = "discarded"

    @property
    def label(self) -> str:
        return {JobState.NEW: _("Nueva"), JobState.FAVORITE: _("Favorita"),
                JobState.APPLIED: _("Postulada"), JobState.DISCARDED: _("Descartada")}[self]


@dataclass
class Job:
    """Una oferta de empleo normalizada, venga de la fuente que venga."""
    key: str                      # «fuente:id», único entre fuentes
    source: str                   # «infojobs», «indeed», «linkedin»
    title: str
    company: str = ""
    location: str = ""
    work_mode: WorkMode = WorkMode.UNKNOWN
    contract: str = ""
    salary_min: float | None = None   # euros brutos anuales, ya normalizado
    salary_max: float | None = None
    salary_text: str = ""             # el texto original, para mostrarlo
    salary_estimated: bool = False    # el portal lo estima, no lo publica la empresa
    experience_text: str = ""
    studies_text: str = ""
    description: str = ""
    full_description: bool = False    # False: ficha resumida (solo requisitos mínimos)
    url: str = ""
    posted: str = ""
    closed: bool = False              # la fuente la marca como expirada
    state: JobState = JobState.NEW

    @property
    def text(self) -> str:
        """Todo el texto en el que se buscan requisitos."""
        return "\n".join(part for part in (self.title, self.experience_text, self.studies_text,
                                           self.description) if part)


@dataclass
class CriterionResult:
    """Un criterio del perfil evaluado frente a una oferta."""
    name: str
    status: Status
    detail: str = ""
    weight: int = 1
    required: bool = False   # imprescindible: si falta, el encaje no puede ser Alto


@dataclass
class Evaluation:
    fit: Fit
    score: float | None
    criteria: list[CriterionResult] = field(default_factory=list)
    category: str = ""

    def count(self, status: Status) -> int:
        return sum(1 for item in self.criteria if item.status is status)

    @property
    def summary(self) -> str:
        """«4 de 6» sobre los criterios que la oferta permite decidir."""
        decided = [item for item in self.criteria if item.status is not Status.UNKNOWN]
        return f"{self.count(Status.MET)}/{len(decided)}" if decided else "—"
