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
    PARTIAL = "partial"  # ◐ lo cubres en parte: tu nivel es menor que lo que pide, o tienes algo parecido

    @property
    def symbol(self) -> str:
        return {Status.MET: "✓", Status.MISSING: "✗", Status.UNKNOWN: "?", Status.PARTIAL: "◐"}[self]


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


class Stage(Enum):
    """En qué punto del proceso de selección está una oferta. Los valores son claves estables."""
    NONE = ""
    IN_PROGRESS = "in_progress"
    FINAL = "final"
    OFFER = "offer"
    HIRED = "hired"
    SUSPENDED = "suspended"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"

    @property
    def label(self) -> str:
        return {Stage.NONE: _("Sin proceso"), Stage.IN_PROGRESS: _("En proceso"), Stage.FINAL: _("Fase final"),
                Stage.OFFER: _("Oferta recibida"), Stage.HIRED: _("Contratado"),
                Stage.SUSPENDED: _("Proceso suspendido"), Stage.REJECTED: _("Rechazado por la empresa"),
                Stage.WITHDRAWN: _("Retirado por mí")}[self]

    @property
    def is_open(self) -> bool:
        """True mientras el proceso sigue vivo."""
        return self in (Stage.IN_PROGRESS, Stage.FINAL, Stage.OFFER)


class EventKind(Enum):
    """Qué ocurrió en un momento del proceso. Los valores son claves estables."""
    CONTACT = "contact"
    INTERVIEW = "interview"
    TEST = "test"
    OFFER = "offer"
    OTHER = "other"

    @property
    def label(self) -> str:
        return {EventKind.CONTACT: _("Contacto"), EventKind.INTERVIEW: _("Entrevista"),
                EventKind.TEST: _("Prueba o examen"), EventKind.OFFER: _("Oferta"),
                EventKind.OTHER: _("Otro")}[self]


@dataclass
class JobEvent:
    """Una línea del histórico de una oferta: qué pasó, cuándo y los detalles."""
    id: int
    day: str            # «AAAA-MM-DD»
    kind: EventKind
    text: str = ""


@dataclass
class Job:
    """Una oferta de empleo normalizada, venga de la fuente que venga."""
    key: str                      # «fuente:id», único entre fuentes
    source: str                   # «infojobs», «indeed», «linkedin», «tecnoempleo», «michaelpage»
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
    notes: str = ""                   # lo que apunta la persona: entrevistas, ofertas recibidas, dudas…
    remind_on: str = ""               # «AAAA-MM-DD»: el día en que quiere que se le recuerde esta oferta
    stage: str = ""                   # clave de Stage: la fase del proceso de selección
    next_steps: str = ""              # lo que toca hacer o esperar a continuación
    event_count: int = 0              # cuántas líneas tiene su histórico

    @property
    def has_tracking(self) -> bool:
        """True si la persona ha apuntado algo de esta oferta: notas, recordatorio, fase, próximos pasos o histórico."""
        return bool(self.notes or self.remind_on or self.stage or self.next_steps or self.event_count)

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
    required: bool = False   # la oferta lo pide como requisito (o en el título): si falta, es un hueco importante
    group: str = "conditions"   # hard (técnica), soft (blanda) o conditions (experiencia, salario, modalidad…)
    credit: float | None = None   # cuánto cubres (0 a 1) cuando el estado es PARTIAL

    @property
    def value(self) -> float:
        """Cuánto aporta a la puntuación: 1 si se cumple, 0 si no, y lo que cubras si es parcial."""
        if self.status is Status.MET:
            return 1.0
        if self.status is Status.PARTIAL:
            return self.credit or 0.0
        return 0.0


@dataclass
class Evaluation:
    fit: Fit
    score: float | None
    criteria: list[CriterionResult] = field(default_factory=list)
    category: str = ""

    def count(self, status: Status) -> int:
        return sum(1 for item in self.criteria if item.status is status)

    def main_gaps(self, limit: int = 3) -> list[str]:
        """Las habilidades que pide la oferta y no cubres del todo, de las que más restan a las que menos."""
        lost = [(item.weight * (1 - item.value), item.name) for item in self.criteria
                if item.group == "hard" and item.status in (Status.MISSING, Status.PARTIAL)]
        return [name for _points, name in sorted(lost, key=lambda pair: (-pair[0], pair[1].casefold()))[:limit]]

    @property
    def summary(self) -> str:
        """«4 de 6» sobre los criterios que la oferta permite decidir."""
        decided = [item for item in self.criteria if item.status is not Status.UNKNOWN]
        return f"{self.count(Status.MET)}/{len(decided)}" if decided else "—"
