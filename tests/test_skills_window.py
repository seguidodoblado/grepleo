import pytest

gi = pytest.importorskip("gi")
cairo = pytest.importorskip("cairo")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from grepleo.profiles import Profile, RadarAxis, SkillRadar
from grepleo.skills_edit import SOFT, SkillGroup, SkillItem, apply_state, state_from_profile
from grepleo.ui.skills_window import SkillsWindow, join_spec, split_spec


def profile():
    radar = SkillRadar("Cloud", [RadarAxis("AWS|amazon web services", 8), RadarAxis("Azure", 2), RadarAxis("GCP", 7)])
    return Profile(name="p", must=["Linux"], nice=["Python"], soft_must=["Liderazgo"], radars=[radar],
                   skill_levels={"linux": 9, "python": 5, "liderazgo": 8})


def make(applied=None):
    return SkillsWindow(Gtk.Window(), state_from_profile(profile()), (applied if applied is not None else []).append)


def test_a_spec_is_split_into_name_and_synonyms_and_joined_back():
    assert split_spec("AWS|amazon web services|aws") == ("AWS", "amazon web services, aws")
    assert split_spec("Git") == ("Git", "") and split_spec("") == ("", "")
    assert join_spec(" AWS ", "amazon web services, aws") == "AWS|amazon web services|aws"
    assert join_spec("Git", "") == "Git" and join_spec("", "") == ""


def test_the_window_lists_the_groups_and_shows_the_skills_of_the_chosen_one_with_their_sliders():
    window = make()
    assert [group.name for group in window.state.groups] == ["Cloud", "Otras habilidades", "Habilidades blandas"]
    assert len(window._rows) == 3 and [round(row.scale.get_value()) for row in window._rows] == [8, 2, 7]
    assert window.group_name.get_visible() and window.group_name.get_text() == "Cloud"
    window._select(window.state.groups[1])                       # «Otras habilidades»: sin nombre editable
    assert not window.group_name.get_visible() and not window.remove_group.get_sensitive()
    assert [row.name.get_text() for row in window._rows] == ["Linux", "Python"]
    assert window.get_resizable() and window.get_transient_for() is None


def test_moving_a_slider_updates_the_skill_the_meaning_and_the_scale_highlight():
    window = make()
    row = window._rows[1]                                         # Azure, nivel 2
    row.scale.set_value(6)
    assert row.item.level == 6 and row.meaning.get_text() == "6 · Lo he usado en trabajo real"
    active = [(low, high) for low, high, box in window.level_rows if box.has_css_class("level-active")]
    assert active == [(5, 6)]                                      # la franja de ese nivel, resaltada en la leyenda
    row.name.set_text("Microsoft Azure")
    row.synonyms.set_text("azure cloud")
    assert row.item.spec == "Microsoft Azure|azure cloud"


def test_skills_are_added_removed_and_shifted_and_a_radar_needs_three_to_eight():
    window = make()
    window._add_skill(SkillItem("Helm", 4))
    assert [item.name for item in window.state.groups[0].skills] == ["AWS", "Azure", "GCP", "Helm"]
    window._shift_all(1)
    assert [item.level for item in window.state.groups[0].skills] == [9, 3, 8, 5]
    window._shift_all(5)                                           # nunca pasa de 10
    assert max(item.level for item in window.state.groups[0].skills) == 10
    window._remove_skill(window._rows[3])
    window._remove_skill(window._rows[2])
    assert "entre 3 y 8" in window.status.get_text()               # con dos, ya no es un radar
    assert not window.preview.get_visible()


def test_radars_are_added_renamed_proposed_and_removed():
    window = make()
    window._add_radar(None)
    assert window._current.kind == "radar" and window._current.name == "" and window.group_name.get_visible()
    window.group_name.set_text("Lenguajes")
    assert window._current.name == "Lenguajes" and "Lenguajes" in window._group_rows[1][0].get_child().get_text()
    window._remove_group(None)
    assert [group.name for group in window.state.groups] == ["Cloud", "Otras habilidades", "Habilidades blandas"]
    soft = window.state.groups[2]
    soft.skills.extend([SkillItem("Empatía", 6), SkillItem("Iniciativa", 6)])
    window._propose(None)                                          # con tres blandas se propone el radar «Blandas»
    assert "Blandas" in [group.name for group in window.state.groups] and "Radares propuestos" in window.message.get_text()
    window._propose(None)
    assert "No hay nada que proponer" in window.message.get_text()


def test_the_catalog_offers_only_what_you_do_not_have_and_adds_it_with_a_default_level():
    window = make()
    window._select(window.state.groups[1])
    window._fill_catalog()
    names = {window._catalog_specs[row].split("|")[0] for row in window._catalog_specs}
    assert "Docker" in names and "Python" not in names and "AWS" not in names      # lo que ya tienes no sale
    row = next(row for row, spec in window._catalog_specs.items() if spec.startswith("Docker"))
    window._catalog_picked(None, row)
    assert window.state.groups[1].skills[-1] == SkillItem("Docker", 5)
    window._select(window.state.groups[2])                         # las blandas ofrecen el vocabulario de blandas
    window._fill_catalog()
    assert any(spec.startswith("comunicación") for spec in window._catalog_specs.values())


def test_apply_hands_over_a_copy_and_cancel_changes_nothing():
    applied = []
    window = make(applied)
    window._rows[0].scale.set_value(3)
    window._apply(None)
    assert len(applied) == 1 and applied[0].groups[0].skills[0].level == 3
    original = state_from_profile(profile())
    untouched = SkillsWindow(Gtk.Window(), original, applied.append)
    untouched._rows[0].scale.set_value(1)
    assert original.groups[0].skills[0].level == 8                 # trabaja sobre una copia
    target = Profile(name="p")
    apply_state(applied[0], target)
    assert target.radars[0].axes[0].level == 3


def test_duplicates_between_groups_are_warned():
    state = state_from_profile(profile())
    state.groups.append(SkillGroup("Otro", "radar", [SkillItem("Azure", 6)]))
    window = SkillsWindow(Gtk.Window(), state, [].append)
    assert "Azure" in window.status.get_text() and "más de un grupo" in window.status.get_text()
    assert SOFT == "soft"
