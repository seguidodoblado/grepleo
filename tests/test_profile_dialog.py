import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from pathlib import Path

from grepleo.profiles import Profile
from grepleo.storage import Store
from grepleo.ui.profile_dialog import ProfileWindow, _text_of


def make_window(profile=None, saved=None):
    parent = Gtk.Window()
    return ProfileWindow(parent, Store(Path(":memory:")), profile, None, (saved if saved is not None else []).append)


def test_the_editor_is_resizable_and_has_a_maximize_button():
    window = make_window()
    assert window.get_resizable() and window.get_titlebar() is not None
    assert window._maximize.get_tooltip_text()


def test_technical_and_soft_skills_are_edited_and_collected_separately():
    profile = Profile(name="DevOps", must=["AWS"], nice=["Terraform"], soft_must=["Trabajo en equipo"],
                      soft_nice=["Comunicación|communication"])
    window = make_window(profile)
    assert _text_of(window._must) == "AWS" and _text_of(window._soft_must) == "Trabajo en equipo"
    window._soft_nice.get_buffer().set_text("Comunicación|communication\nEmpatía", -1)
    collected = window._collect()
    assert collected.must == ["AWS"] and collected.nice == ["Terraform"]
    assert collected.soft_must == ["Trabajo en equipo"]
    assert collected.soft_nice == ["Comunicación|communication", "Empatía"]


def test_saving_stores_the_soft_skills_and_needs_a_name():
    saved = []
    window = make_window(None, saved)
    window._on_save(None)
    assert window._error.get_text() and saved == []        # sin nombre no se guarda
    window._name.set_text("Nuevo")
    window._soft_must.get_buffer().set_text("Liderazgo", -1)
    window._on_save(None)
    assert len(saved) == 1
    stored = window._store.list_profiles()[0][1]
    assert stored.soft_must == ["Liderazgo"]


def test_the_radar_sliders_start_from_the_profile_and_only_changes_are_stored():
    profile = Profile(name="R", years=6, must=["AWS", "Docker"])
    window = make_window(profile)
    assert window._radar_scales["experience"].get_value() == 6 and window._radar_scales["technical"].get_value() == 2
    assert window._collect().radar == {}                    # sin tocar nada, sigue calculándose del perfil
    window._radar_scales["technical"].set_value(9)
    assert window._collect().radar == {"technical": 9}
    window._years.set_value(10)                             # el perfil cambia: lo no tocado se recalcula
    assert window._collect().radar == {"technical": 9}
    window._reset_radar(None)
    assert window._radar_scales["technical"].get_value() == 2 and window._radar_scales["experience"].get_value() == 10
    assert window._collect().radar == {}


def test_a_saved_radar_is_restored_in_the_sliders():
    profile = Profile(name="R", years=6, radar={"soft": 8})
    window = make_window(profile)
    assert window._radar_scales["soft"].get_value() == 8


def test_the_cv_section_is_edited_collected_and_the_uploaded_file_can_be_cleared():
    profile = Profile(name="CV", full_name="Ana Pérez", email="ana@example.org", experience="SRE en ACME",
                      cv_file="/tmp/mi-cv.pdf")
    window = make_window(profile)
    assert window._full_name.get_text() == "Ana Pérez" and window._cv_label.get_text() == "/tmp/mi-cv.pdf"
    window._phone.set_text(" 600 000 000 ")
    window._education.get_buffer().set_text("Grado en Informática", -1)
    collected = window._collect()
    assert (collected.full_name, collected.email, collected.phone) == ("Ana Pérez", "ana@example.org", "600 000 000")
    assert collected.experience == "SRE en ACME" and collected.education == "Grado en Informática"
    assert collected.cv_file == "/tmp/mi-cv.pdf"
    window._set_cv_file("")
    assert window._collect().cv_file == "" and window._cv_label.get_text() == "Ninguno"


def test_topic_radars_are_edited_in_the_dialog_and_stored_with_the_profile():
    from grepleo.profiles import RadarAxis, SkillRadar
    profile = Profile(name="R", must=["AWS", "Docker", "Terraform"],
                      radars=[SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Docker", 5), RadarAxis("Helm", 2)])])
    window = make_window(profile)
    assert [row.name.get_text() for row in window._topic_radars.rows] == ["Cloud"]
    window._topic_radars.rows[0].text.get_buffer().set_text("AWS = 9\nDocker = 6\nHelm = 3", -1)
    assert window._collect().radars[0].axes[0] == RadarAxis("AWS", 9)
    window._topic_radars.add(SkillRadar("Lenguajes", [RadarAxis("Python", 7), RadarAxis("Bash", 5), RadarAxis("SQL", 4)]))
    window._name.set_text("Guardado")
    saved = []
    window._on_saved = saved.append
    window._on_save(None)
    stored = window._store.list_profiles()[0][1]
    assert [radar.name for radar in stored.radars] == ["Cloud", "Lenguajes"] and saved


def test_links_are_edited_one_per_line_and_blank_lines_are_dropped():
    window = make_window(Profile(name="L", links="linkedin.com/in/ana\ngithub.com/ana"))
    assert _text_of(window._links) == "linkedin.com/in/ana\ngithub.com/ana"
    window._links.get_buffer().set_text("  linkedin.com/in/ana \n\n github.com/ana\nana.dev  ", -1)
    assert window._collect().links == "linkedin.com/in/ana\ngithub.com/ana\nana.dev"


def test_professional_profiles_have_a_box_each_that_cleans_completes_and_warns():
    from gi.repository import Gtk

    from grepleo.links import PLATFORM_IDS
    window = make_window(Profile(name="N", networks={"github": "github.com/ana"}))
    assert tuple(window._networks) == PLATFORM_IDS and window._networks["github"].get_text() == "github.com/ana"
    window._networks["linkedin"].set_text("ana-perez")                       # solo el usuario
    window._networks["bluesky"].set_text("https://www.bsky.app/profile/ana.bsky.social/?x=1")
    window._networks["web"].set_text("https://ana.dev/")
    window._networks["gitlab"].set_text("github.com/otra")                   # de otra plataforma
    assert window._networks["gitlab"].get_icon_name(Gtk.EntryIconPosition.SECONDARY)    # con aviso
    assert not window._networks["github"].get_icon_name(Gtk.EntryIconPosition.SECONDARY)
    window._tidy_network("bluesky")
    assert window._networks["bluesky"].get_text() == "bsky.app/profile/ana.bsky.social"
    collected = window._collect().networks
    assert collected == {"linkedin": "linkedin.com/in/ana-perez", "github": "github.com/ana",
                         "bluesky": "bsky.app/profile/ana.bsky.social", "web": "ana.dev", "gitlab": "github.com/otra"}
    window._networks["github"].set_text("")
    assert "github" not in window._collect().networks                        # una casilla vacía no se guarda
