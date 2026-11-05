"""El mapa del mercado: los radares de tu perfil frente a lo que piden, de media, las ofertas que estás viendo.

Para cada eje de cada radar se mira cuántas ofertas (con descripción completa) lo piden y, entre las que lo piden, cuánto
(la misma escala de 5, 7 y 10 de los radares). La demanda que se dibuja es esa media **entre las que lo piden**: así una
tecnología que solo cita el 20 % de las ofertas, pero siempre como requisito, no se diluye hasta parecer que nadie la
pide; cuántas la piden va en la nota de cada eje y es el peso de ese eje en el solape: lo que piden pocas ofertas pesa
poco. Sin GTK.
"""
from __future__ import annotations

from dataclasses import dataclass

from .i18n import _
from .models import Evaluation, Fit, Job
from .profiles import MAX_AXES, MIN_AXES, Profile, parse_term
from .radar import (
    AXES,
    RadarData,
    _general_notes,
    axis_labels,
    build_radars,
    data_levels,
    demand_note,
    general_levels,
    offer_demand,
    term_demand,
    total_overlap,
)
from .textutil import mentions, normalize


@dataclass
class Market:
    radars: list[RadarData]
    offers: int        # ofertas con descripción completa sobre las que se ha calculado
    seen: int          # ofertas que se pasaron (con o sin descripción completa)


def _share_note(asking: int, total: int, how: str) -> str:
    share = round(100 * asking / total) if total else 0
    if not asking:
        return _("ninguna oferta lo pide")
    return _("en el {share} % de las ofertas · {how}").format(share=share, how=how)


@dataclass
class OfferRow:
    """Una oferta del mercado con sus valores: su encaje y lo que cubres de ella en cada radar y en conjunto."""
    job: Job
    fit: Fit
    score: float | None
    overall: float | None                 # el solape global de esta oferta (todos los radares juntos)
    overlaps: list[float | None]          # el solape de cada radar, en el orden de `Market.radars`


def build_rows(jobs: list[Job], evaluations: dict[str, Evaluation], profile: Profile) -> list[OfferRow]:
    """El desglose por oferta de lo que cuenta el mapa del mercado (las de descripción completa), de más a menos cubierta."""
    rows = []
    for job in jobs:
        if not job.full_description:
            continue
        radars = build_radars(job, profile)
        evaluation = evaluations.get(job.key)
        rows.append(OfferRow(job, evaluation.fit if evaluation else Fit.UNKNOWN, evaluation.score if evaluation else None,
                             total_overlap(radars), [radar.overlap for radar in radars]))
    rows.sort(key=lambda row: (-(row.overall if row.overall is not None else -1), row.job.company.casefold()))
    return rows


def relevant_jobs(jobs: list[Job], evaluations: dict[str, Evaluation]) -> list[Job]:
    """Las ofertas de encaje alto o medio."""
    return [job for job in jobs if job.key in evaluations and evaluations[job.key].fit in (Fit.HIGH, Fit.MEDIUM)]


def low_fit_jobs(jobs: list[Job], evaluations: dict[str, Evaluation]) -> list[Job]:
    """Las ofertas de encaje bajo: lo que piden y te falta, que es lo que hay que estudiar para llegar a ellas."""
    return [job for job in jobs if job.key in evaluations and evaluations[job.key].fit is Fit.LOW]


def build_market(jobs: list[Job], profile: Profile) -> Market:
    """Los radares del perfil (el general y los de tema) con la demanda media de las ofertas dadas."""
    detailed = [job for job in jobs if job.full_description]
    if not detailed:
        return Market([], 0, len(jobs))
    return Market([_general(detailed, profile), *_topics(detailed, profile)], len(detailed), len(jobs))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _general(jobs: list[Job], profile: Profile) -> RadarData:
    """El radar general del mercado: la demanda de cada eje es la media entre las ofertas que lo piden; en técnicas y
    blandas, tu lado es esa media por la parte que cubres de lo que piden esas ofertas (como en cada oferta)."""
    labels = axis_labels()
    per_job = []
    for job in jobs:
        asked = offer_demand(job, profile)
        per_job.append((asked, general_levels(job, profile, asked)))
    demand: dict[str, float | None] = {}
    levels = data_levels(profile)
    counts = {}
    for axis in AXES:
        pairs = [(asked[axis], mine[axis]) for asked, mine in per_job if asked[axis]]   # las que lo piden
        counts[axis] = len(pairs)
        mean = _mean([value for value, _mine in pairs])
        demand[axis] = mean
        if axis in ("technical", "soft"):   # lo que cubres de lo que piden: Σ tu lado / Σ lo que piden, a la altura de la media
            total = sum(value for value, _mine in pairs)
            levels[axis] = mean * sum(mine for _value, mine in pairs) / total if total else 0.0
    notes = [_share_note(counts[axis], len(jobs), text) for axis, text in zip(AXES, _general_notes(demand), strict=True)]
    return RadarData(_("General"), [labels[axis] for axis in AXES], [levels[axis] for axis in AXES],
                     [demand[axis] for axis in AXES], notes, [counts[axis] / len(jobs) for axis in AXES])


def _topics(jobs: list[Job], profile: Profile) -> list[RadarData]:
    texts = [normalize(job.text) for job in jobs]
    radars = []
    for radar in profile.radars:
        axes = [axis for axis in radar.axes if axis.name][:MAX_AXES]
        if len(axes) < MIN_AXES:
            continue
        demand, notes, weights = [], [], []
        for axis in axes:
            names = parse_term(axis.spec)[1]
            values = []
            for job, text in zip(jobs, texts, strict=True):
                if mentions(text, names) and (value := term_demand(job, axis.spec)):
                    values.append(value)
            mean = _mean(values)
            demand.append(mean)
            weights.append(len(values) / len(jobs))
            notes.append(_share_note(len(values), len(jobs), demand_note(mean) if values else ""))
        radars.append(RadarData(radar.name, [axis.name for axis in axes], [float(axis.level) for axis in axes],
                                demand, notes, weights))
    return radars
