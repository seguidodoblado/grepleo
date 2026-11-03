from pathlib import Path

from grepleo import settings


def test_without_a_file_everything_follows_the_defaults(tmp_path: Path):
    missing = tmp_path / "no-existe.json"
    assert settings.read_settings(missing) == {} and settings.language(missing) is None
    assert settings.dark_mode(missing) is None and settings.budget_usd(missing) == settings.DEFAULT_BUDGET_USD


def test_values_are_saved_and_read_back(tmp_path: Path):
    path = tmp_path / "config" / "settings.json"
    settings.write_settings({"language": "en", "dark_mode": True, "budget_usd": 2.5}, path)
    assert settings.language(path) == "en" and settings.dark_mode(path) is True
    assert settings.budget_usd(path) == 2.5
    settings.write_settings({"dark_mode": None}, path)
    assert settings.dark_mode(path) is None


def test_unknown_or_wrong_values_and_broken_files_are_ignored(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text('{"language": "klingon", "dark_mode": "si", "budget_usd": -3}', encoding="utf-8")
    assert settings.language(path) is None and settings.dark_mode(path) is None
    assert settings.budget_usd(path) == settings.DEFAULT_BUDGET_USD
    path.write_text('{"budget_usd": true}', encoding="utf-8")
    assert settings.budget_usd(path) == settings.DEFAULT_BUDGET_USD
    path.write_text("esto no es json", encoding="utf-8")
    assert settings.read_settings(path) == {}
    path.write_text("[1, 2]", encoding="utf-8")
    assert settings.read_settings(path) == {}
