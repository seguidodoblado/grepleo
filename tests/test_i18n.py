import gettext
import string

import pytest

from grepleo import i18n
from grepleo.i18n import _
from grepleo.models import Fit, JobState, Status, WorkMode

MO = i18n.LOCALE_DIR / "en" / "LC_MESSAGES" / f"{i18n.DOMAIN}.mo"
PO = i18n.LOCALE_DIR.parents[2] / "po" / "en.po"
needs_catalog = pytest.mark.skipif(not MO.exists(), reason="Falta compilar po/en.po (ver po/README.md)")


def english():
    return gettext.translation(i18n.DOMAIN, localedir=str(i18n.LOCALE_DIR), languages=["en"])


def placeholders(text):
    return {name for _literal, name, _spec, _conv in string.Formatter().parse(text) if name}


def test_spanish_is_the_source_language_and_needs_no_catalog():
    assert _("Preferencias") == "Preferencias"
    assert Fit.HIGH.label == "Alto" and WorkMode.HYBRID.label == "Híbrido"
    assert JobState.FAVORITE.label == "Favorita"


def test_enum_values_stay_stable_keys():
    """El código, la base de datos y las pruebas comparan estos valores: traducirlos los rompería."""
    assert [m.value for m in WorkMode] == ["remote", "hybrid", "onsite", "unknown"]
    assert [f.value for f in Fit] == ["high", "medium", "low", "unknown"]
    assert [s.value for s in Status] == ["met", "missing", "unknown", "partial"]
    assert [s.value for s in JobState] == ["new", "favorite", "applied", "discarded"]


@needs_catalog
def test_english_catalog_translates():
    translation = english()
    assert translation.gettext("Preferencias") == "Preferences"
    assert translation.gettext("Alto") == "High"
    assert translation.ngettext("{count} oferta es en remoto.", "{count} ofertas son en remoto.", 1) == \
        "{count} offer is remote."
    assert translation.ngettext("{count} oferta es en remoto.", "{count} ofertas son en remoto.", 3) == \
        "{count} offers are remote."


@needs_catalog
def test_translator_credits_entry_is_filled():
    assert "@" in english().gettext("translator-credits")


@needs_catalog
def test_every_translation_keeps_the_placeholders_of_the_original():
    """Si el inglés perdiera un {nombre}, .format() fallaría en pleno uso."""
    translation = english()
    messages = [m for m in translation._catalog if isinstance(m, str) and m]
    assert messages
    for message in messages:
        assert placeholders(translation.gettext(message)) == placeholders(message), message


@needs_catalog
def test_no_message_is_left_untranslated():
    text = PO.read_text(encoding="utf-8")
    assert "fuzzy" not in text
    assert 'msgstr ""\n\n' not in text.split('"Plural-Forms')[1]
