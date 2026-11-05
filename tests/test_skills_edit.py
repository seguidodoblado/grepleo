from grepleo.profiles import Profile, RadarAxis, SkillRadar
from grepleo.skills_edit import (
    OTHER,
    RADAR,
    SOFT,
    SkillGroup,
    SkillItem,
    SkillsState,
    apply_state,
    key_question,
    level_meaning,
    level_scale,
    level_title,
    state_from_profile,
)


def profile():
    radar = SkillRadar("Cloud", [RadarAxis("AWS|amazon web services", 8), RadarAxis("Azure", 2), RadarAxis("GCP", 7)])
    return Profile(name="p", must=["AWS|amazon web services", "Linux"], nice=["Python"], soft_must=["Liderazgo"],
                   soft_nice=["Empatía"], radars=[radar],
                   skill_levels={"aws": 8, "linux": 9, "python": 5, "liderazgo": 8, "empatia": 6})


def test_the_groups_are_the_radars_the_other_technical_skills_and_the_soft_ones():
    state = state_from_profile(profile())
    assert [(group.kind, group.name) for group in state.groups] == [
        (RADAR, "Cloud"), (OTHER, "Otras habilidades"), (SOFT, "Habilidades blandas")]
    assert [(item.name, item.level) for item in state.groups[1].skills] == [("Linux", 9), ("Python", 5)]   # AWS ya está en un radar
    assert [(item.name, item.level) for item in state.groups[2].skills] == [("Liderazgo", 8), ("Empatía", 6)]


def test_applying_the_groups_writes_the_levels_and_the_lists_and_survives_a_round_trip():
    original = profile()
    state = state_from_profile(original)
    state.groups[1].skills.append(SkillItem("Docker", 4))
    state.groups[2].skills[0].level = 5
    target = Profile(name="p")
    apply_state(state, target)
    assert target.radars == original.radars
    assert target.must == ["AWS|amazon web services", "Azure|", "GCP", "Linux"][:0] or "Linux" in target.must
    assert "AWS|amazon web services" in target.must and "Azure" in target.nice and "Docker" in target.nice
    assert target.skill_levels["docker"] == 4 and target.skill_levels["liderazgo"] == 5
    assert target.soft_nice == ["Liderazgo", "Empatía"] and target.soft_must == []      # con un 5, ya no «dominas»
    again = state_from_profile(target)
    assert [(g.kind, [(i.spec, i.level) for i in g.skills]) for g in again.groups] == [
        (g.kind, [(i.spec, i.level) for i in g.skills]) for g in state.groups]


def test_duplicates_between_groups_are_detected_and_the_first_wins_when_saving():
    state = SkillsState([SkillGroup("CI/CD", RADAR, [SkillItem("Azure DevOps", 4)]),
                         SkillGroup("Control de versiones", RADAR, [SkillItem("Azure DevOps|Azure Repos", 6)]),
                         SkillGroup("Otras", OTHER, [SkillItem("", 5)])])
    assert state.duplicates() == ["Azure DevOps"]
    target = Profile(name="p")
    apply_state(state, target)
    assert target.skill_levels["azure devops"] == 4 and target.nice == ["Azure DevOps"]      # una sola vez, la primera


def test_empty_skills_and_radars_are_dropped_and_an_unnamed_radar_is_called_radar():
    state = SkillsState([SkillGroup("", RADAR, [SkillItem("Scrum", 5)]), SkillGroup("", RADAR, []),
                         SkillGroup("Vacío", RADAR, [SkillItem(" ", 3)])])
    target = Profile(name="p")
    apply_state(state, target)
    assert [radar.name for radar in target.radars] == ["Radar", "Vacío"] and target.radars[1].axes == []


def test_the_scale_covers_every_level_once_and_says_what_each_one_means():
    scale = level_scale()
    covered = [level for low, high, _title, _meaning in scale for level in range(low, high + 1)]
    assert covered == list(range(11))
    assert level_title(6) == "Lo he usado en trabajo real" and level_title(5) == level_title(6)
    assert "requisito" in level_meaning(8) and "«se valora»" in level_meaning(7)
    assert level_title(99) == "" and level_meaning(-1) == ""


def test_soft_skills_have_their_own_scale_that_talks_about_practice_not_about_tools():
    technical, soft = level_scale(), level_scale(soft=True)
    covered = [level for low, high, _title, _meaning in soft for level in range(low, high + 1)]
    assert covered == list(range(11)) and len(soft) != len(technical)
    assert level_title(6, soft=True) == "Lo practico con naturalidad" == level_title(7, soft=True)
    assert level_title(6) == "Lo he usado en trabajo real"
    text = " ".join(title + meaning for _low, _high, title, meaning in soft).lower()
    for tool_word in ("documentación", "producción", "diseño", "laboratorio", "tutorial", "requisito"):
        assert tool_word not in text                                          # nada de lo que se aplica a las herramientas
    assert "ejemplo" in key_question(soft=True) and "requisito" in key_question()
    assert "Cubre del todo" in level_meaning(6, soft=True)                      # coincide con SOFT_DEMAND: desde 6, cubierta
