"""Ajustes del usuario, en ~/.config/grepleo/settings.json: idioma, tema y gasto máximo por búsqueda."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

LANGUAGES = ("es", "en")   # idiomas que se pueden elegir en Preferencias (None: el del sistema)
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "grepleo"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
DEFAULT_BUDGET_USD = 1.0   # tope de gasto en Apify por búsqueda, repartido entre las fuentes


def read_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def dark_mode(path: Path = SETTINGS_PATH) -> bool | None:
    """El tema elegido (True oscuro, False claro), o None para seguir el del sistema."""
    value = read_settings(path).get("dark_mode")
    return value if isinstance(value, bool) else None


def language(path: Path = SETTINGS_PATH) -> str | None:
    """El idioma elegido, o None para seguir el del sistema (un valor desconocido se ignora)."""
    value = read_settings(path).get("language")
    return value if value in LANGUAGES else None


def budget_usd(path: Path = SETTINGS_PATH) -> float:
    """Gasto máximo por búsqueda en dólares; un valor no numérico o no positivo vuelve al predeterminado."""
    value = read_settings(path).get("budget_usd")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return DEFAULT_BUDGET_USD
    return float(value)
