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
from grepleo.ui.radar_editor import RadarEditor


def make(radars=None, profile=None):
    profile = profile or Profile(name="p")
    return RadarEditor(radars or [], lambda: profile)


def test_radars_are_added_edited_and_removed_and_the_preview_follows_the_text():
    editor = make([SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Docker", 5), RadarAxis("Helm", 2)])])
    row = editor.rows[0]
    assert row.status.get_text() == "" and "AWS" in row.preview.get_tooltip_text()
    row.text.get_buffer().set_text("AWS = 9\nDocker", -1)
    assert "entre 3 y 8" in row.status.get_text()               # con dos elementos no es un radar
    row.text.get_buffer().set_text("AWS = 9\nDocker\nHelm = 1\nGit", -1)
    assert row.status.get_text() == ""
    assert editor.radars() == [SkillRadar("Cloud", [RadarAxis("AWS", 9), RadarAxis("Docker", 5),
                                                    RadarAxis("Helm", 1), RadarAxis("Git", 5)])]
    editor.add(SkillRadar(""))
    assert len(editor.rows) == 2 and len(editor.radars()) == 1   # la fila vacía no cuenta
    editor.rows[1].text.get_buffer().set_text("Scrum\nKanban\nJira", -1)
    assert editor.radars()[1].name == "Radar"                    # sin nombre se llama «Radar»
    editor._remove(editor.rows[0])
    assert [radar.name for radar in editor.radars()] == ["Radar"]


def test_radars_are_proposed_from_the_profile_without_repeating_existing_ones():
    profile = Profile(name="p", must=["AWS", "Docker", "Terraform"], soft_must=["Liderazgo", "Empatía", "Iniciativa"])
    editor = make(profile=profile)
    editor._propose(None)
    names = [radar.name for radar in editor.radars()]
    assert "Cloud" in names and "Blandas" in names and "Radares propuestos" in editor.message.get_text()
    editor._propose(None)                                        # una segunda vez no duplica
    assert [radar.name for radar in editor.radars()] == names and "No hay nada que proponer" in editor.message.get_text()


def test_an_empty_profile_has_nothing_to_propose():
    editor = make()
    editor._propose(None)
    assert editor.rows == [] and "No hay nada que proponer" in editor.message.get_text()
