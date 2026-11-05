"""Traducciones con gettext: el idioma fuente es el español; el resto, en po/*.po.

El dominio se liga a esta carpeta al importar el módulo, de modo que `_()` ya funciona en las
constantes de módulo; `install()` solo ajusta el locale del proceso (para los textos propios de
GTK) y se llama una vez al arrancar. El idioma sale de Ajustes, del sistema o de `$LANGUAGE`.
"""
from __future__ import annotations

import gettext
import locale
import os
from functools import lru_cache
from pathlib import Path

DOMAIN = "grepleo"
LOCALE_DIR = Path(__file__).parent

gettext.bindtextdomain(DOMAIN, str(LOCALE_DIR))


def install() -> None:
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass  # locale del sistema no instalado: seguimos con el idioma por defecto (es)
    gettext.bindtextdomain(DOMAIN, str(LOCALE_DIR))
    gettext.textdomain(DOMAIN)


@lru_cache(maxsize=8)
def _translation(_environment: tuple[str, ...]) -> gettext.NullTranslations:
    """El catálogo para el idioma en uso. `gettext.dgettext` lo busca en disco en cada llamada (decenas de `stat`),
    y con miles de textos por segundo en la evaluación eso se notaba; aquí se busca una vez por idioma."""
    return gettext.translation(DOMAIN, str(LOCALE_DIR), fallback=True)


def _catalog() -> gettext.NullTranslations:
    return _translation(tuple(os.environ.get(name, "") for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")))


def _(message: str) -> str:
    return _catalog().gettext(message)


def ngettext(singular: str, plural: str, count: int) -> str:
    return _catalog().ngettext(singular, plural, count)
