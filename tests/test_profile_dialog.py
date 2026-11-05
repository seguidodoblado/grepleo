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

from gi.repository import GLib

from grepleo.profiles import Profile
from grepleo.storage import Store
from grepleo.ui.profile_dialog import ProfileWindow, _text_of


def make_window(profile=None, saved=None):
    parent = Gtk.Window()
    return ProfileWindow(parent, Store(Path(":memory:")), profile, None, (saved if saved is not None else []).append)


def test_the_editor_is_an_independent_resizable_window_that_blocks_the_main_one_while_open():
    parent = Gtk.Window()
    window = ProfileWindow(parent, Store(Path(":memory:")), None, None, [].append)
    # con ventana madre o modal, el gestor de ventanas la trata como un diálogo y no deja maximizarla
    assert window.get_resizable() and window.get_transient_for() is None and not window.get_modal()
    window.present()
    context = GLib.MainContext.default()
    while context.iteration(False):
        pass
    assert not parent.get_sensitive()
    window.close()
    while context.iteration(False):
        pass
    assert parent.get_sensitive()                    # al cerrarla, la principal vuelve a responder


def test_the_skills_come_from_the_skills_window_with_their_levels_and_radars():
    from grepleo.profiles import RadarAxis, SkillRadar
    profile = Profile(name="DevOps", must=["AWS"], nice=["Terraform"], soft_must=["Trabajo en equipo"],
                      radars=[SkillRadar("Cloud", [RadarAxis("AWS", 8), RadarAxis("Azure", 2), RadarAxis("GCP", 7)])],
                      skill_levels={"aws": 8, "terraform": 4, "trabajo en equipo": 8})
    window = make_window(profile)
    assert "4 habilidades técnicas" in window._skills_summary.get_text() and "1 blandas" in window._skills_summary.get_text()
    collected = window._collect()
    assert collected.radars == profile.radars and collected.skill_levels["terraform"] == 4
    assert "Terraform" in collected.nice and "Trabajo en equipo" in collected.soft_must
    window._skills.group("other").skills[0].level = 9           # lo que cambia la ventana «Habilidades»
    assert window._collect().skill_levels["terraform"] == 9 and "Terraform" in window._collect().must


def test_saving_stores_the_skills_and_needs_a_name():
    from grepleo.skills_edit import SkillItem
    saved = []
    window = make_window(None, saved)
    window._on_save(None)
    assert window._error.get_text() and saved == []        # sin nombre no se guarda
    window._name.set_text("Nuevo")
    window._skills.group("soft").skills.append(SkillItem("Liderazgo", 8))
    window._on_save(None)
    assert len(saved) == 1
    stored = window._store.list_profiles()[0][1]
    assert stored.soft_must == ["Liderazgo"] and stored.skill_levels == {"liderazgo": 8}


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


def test_a_bare_level_in_languages_shows_a_warning_that_says_what_to_write():
    window = make_window(Profile(name="I", languages={"Inglés": "B2"}))
    assert not window._languages_warning.get_visible()
    window._languages.set_text("A2")
    assert window._languages_warning.get_visible()
    assert "«A2» es un nivel, no un idioma" in window._languages_warning.get_text() and "Inglés A2" in window._languages_warning.get_text()
    window._languages.set_text("Inglés A2, Francés B1")
    assert not window._languages_warning.get_visible()
    assert make_window(Profile(name="J", languages={"A2": ""}))._languages_warning.get_visible()   # un perfil ya guardado mal
