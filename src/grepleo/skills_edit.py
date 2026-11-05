"""Lo que edita la ventana «Habilidades»: tus habilidades por grupos, cada una con su nivel de 0 a 10.

Un grupo es un radar por tema (Cloud, Lenguajes…), «Otras habilidades» (las técnicas que no están en ningún radar) o las
blandas. Esto es la parte sin GTK: pasar del perfil a los grupos y de los grupos al perfil, con la escala de niveles que
explica cada número. Sin GTK.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .i18n import _
from .profiles import DOMINANT_FROM, MAX_AXES, Profile, RadarAxis, SkillRadar, parse_term, skill_key
from .similar import aliases

RADAR, OTHER, SOFT = "radar", "other", "soft"   # las clases de grupo


def other_name() -> str:
    return _("Otras habilidades")


def soft_name() -> str:
    return _("Habilidades blandas")


@dataclass
class SkillItem:
    spec: str          # «AWS|amazon web services»: el nombre y, tras |, sus sinónimos
    level: int = 5

    @property
    def name(self) -> str:
        return parse_term(self.spec)[0]


@dataclass
class SkillGroup:
    name: str
    kind: str = RADAR
    skills: list[SkillItem] = field(default_factory=list)


@dataclass
class SkillsState:
    groups: list[SkillGroup] = field(default_factory=list)

    def group(self, kind: str) -> SkillGroup:
        """El grupo de una clase única («otras» o «blandas»): se crea si falta."""
        found = next((item for item in self.groups if item.kind == kind), None)
        if found is None:
            found = SkillGroup(other_name() if kind == OTHER else soft_name(), kind)
            self.groups.append(found)
        return found

    def duplicates(self) -> list[str]:
        """Las habilidades técnicas que están en más de un grupo (cuenta el nombre y sus sinónimos)."""
        seen: dict[str, str] = {}
        repeated: list[str] = []
        for group in self.groups:
            if group.kind == SOFT:
                continue
            for skill in group.skills:
                names = aliases(skill.spec)
                if any(name in seen for name in names):
                    repeated.append(skill.name)
                seen.update({name: group.name for name in names})
        return repeated


def state_from_profile(profile: Profile) -> SkillsState:
    """Los grupos de un perfil: sus radares, «Otras habilidades» con lo técnico que no está en ningún radar y las blandas."""
    groups = [SkillGroup(radar.name, RADAR, [SkillItem(axis.spec, axis.level) for axis in radar.axes])
              for radar in profile.radars]
    in_radars = set()
    for radar in profile.radars:
        for axis in radar.axes:
            in_radars |= aliases(axis.spec)
    others = [SkillItem(spec, level) for spec, level in profile.technical_levels()
              if aliases(spec) and not aliases(spec) & in_radars]
    groups.append(SkillGroup(other_name(), OTHER, others))
    groups.append(SkillGroup(soft_name(), SOFT, [SkillItem(spec, level) for spec, level in profile.soft_levels()]))
    return SkillsState(groups)


def apply_state(state: SkillsState, profile: Profile) -> None:
    """Escribe los grupos en el perfil: sus radares, las listas «dominas» (desde nivel 7) y «conoces», y el nivel de cada
    habilidad. Las listas llevan todas las técnicas, también las de los radares, para el resto de la aplicación."""
    radars = []
    technical: list[SkillItem] = []
    for group in state.groups:
        if group.kind == RADAR:
            skills = [item for item in group.skills if item.name]
            if group.name.strip() or skills:
                radars.append(SkillRadar(group.name.strip() or _("Radar"),
                                         [RadarAxis(item.spec, item.level) for item in skills[:MAX_AXES]]))
        if group.kind in (RADAR, OTHER):
            technical.extend(item for item in group.skills if item.name)
    soft = [item for group in state.groups if group.kind == SOFT for item in group.skills if item.name]
    profile.radars = radars
    profile.must, profile.nice, profile.soft_must, profile.soft_nice = [], [], [], []
    profile.skill_levels = {}
    for items, must, nice in ((technical, profile.must, profile.nice), (soft, profile.soft_must, profile.soft_nice)):
        seen: set[str] = set()
        for item in items:
            key = skill_key(item.spec)
            if key in seen:
                continue
            seen.add(key)
            (must if item.level >= DOMINANT_FROM else nice).append(item.spec)
            profile.skill_levels[key] = item.level


# --- la escala de niveles --------------------------------------------------------------------------------
# (desde, hasta, título, qué significa): la misma tabla que se usa para valorarse; la pregunta de fondo es «¿me presentaría a
# una oferta que lo pide como requisito y lo defendería en la entrevista?»
def level_scale() -> list[tuple[int, int, str, str]]:
    return [
        (0, 0, _("No lo conozco"), _("No lo he usado ni sé qué es.")),
        (1, 2, _("Lo conozco de oídas"), _("Sé qué es y para qué sirve, o lo he visto en una demostración; no lo he usado.")),
        (3, 4, _("Lo he probado"), _("Lo he usado en laboratorios o tutoriales, siguiendo guías; con un caso real "
                                     "necesitaría ayuda.")),
        (5, 6, _("Lo he usado en trabajo real"), _("Con la documentación al lado resuelvo lo habitual; todavía no lo "
                                                   "diseño de cero.")),
        (7, 7, _("Lo uso con soltura"), _("En producción, con autonomía. Cubre del todo lo que una oferta pide como "
                                          "«se valora».")),
        (8, 8, _("Lo diseño y lo mantengo"), _("Lo diseño, configuro y mantengo solo y resuelvo incidencias. Cubre un "
                                               "requisito: me presentaría y lo defendería con casos reales.")),
        (9, 9, _("Dominio profundo"), _("Arquitectura, optimización y casos complejos; puedo enseñarlo a otros.")),
        (10, 10, _("Referente"), _("Reconocido en el tema: contribuciones o años de especialización.")),
    ]


def level_title(level: int) -> str:
    """«Lo he usado en trabajo real» para un 5 o un 6: el título de la franja de ese nivel."""
    for low, high, title, _meaning in level_scale():
        if low <= level <= high:
            return title
    return ""


def level_meaning(level: int) -> str:
    for low, high, _title, meaning in level_scale():
        if low <= level <= high:
            return meaning
    return ""
