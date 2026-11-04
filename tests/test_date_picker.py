import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    if not Gtk.init_check():
        pytest.skip("sin pantalla para crear widgets", allow_module_level=True)
except (ValueError, ImportError):
    pytest.skip("GTK 4 no disponible", allow_module_level=True)

from datetime import timedelta

from grepleo.ui.date_picker import DatePicker, today


def test_choosing_shortcuts_and_clearing_notify_and_update_the_button():
    chosen = []
    picker = DatePicker(chosen.append)
    assert picker.day == "" and picker.button.get_label() and not picker.clear_button.get_sensitive()
    in_three = today() + timedelta(days=3)
    picker.choose(in_three)
    assert chosen == [in_three.isoformat()] and picker.button.get_label() == in_three.isoformat()
    assert picker.clear_button.get_sensitive()
    picker.clear_button.emit("clicked")
    assert chosen[-1] == "" and picker.day == ""


def test_setting_a_day_from_code_does_not_notify_and_a_picker_can_have_no_clear_button():
    chosen = []
    picker = DatePicker(chosen.append, clearable=False, shortcuts=False)
    picker.set_day("2026-11-20")
    assert picker.day == "2026-11-20" and chosen == [] and picker.clear_button is None
