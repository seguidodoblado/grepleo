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
    demand_note,
    offer_demand,
    profile_levels,
    term_demand,
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


def relevant_jobs(jobs: list[Job], evaluations: dict[str, Evaluation]) -> list[Job]:
    """Las ofertas de encaje alto o medio."""
    return [job for job in jobs if job.key in evaluations and evaluations[job.key].fit in (Fit.HIGH, Fit.MEDIUM)]


def build_market(jobs: list[Job], profile: Profile) -> Market:
    """Los radares del perfil (el general y los de tema) con la demanda media de las ofertas dadas."""
    detailed = [job for job in jobs if job.full_description]
    if not detailed:
        return Market([], 0, len(jobs))
    return Market([_general(detailed, profile), *_topics(detailed, profile)], len(detailed), len(jobs))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _general(jobs: list[Job], profile: Profile) -> RadarData:
    asked = [offer_demand(job, profile) for job in jobs]
    levels, labels = profile_levels(profile), axis_labels()
    demand: dict[str, float | None] = {}
    notes = []
    counts = {}
    for axis in AXES:
        values = [item[axis] for item in asked if item[axis]]    # las que lo piden (None y 0 quedan fuera)
        counts[axis] = len(values)
        demand[axis] = _mean(values)
    detail = _general_notes(demand)
    for axis, text in zip(AXES, detail, strict=True):
        notes.append(_share_note(counts[axis], len(jobs), text))
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
