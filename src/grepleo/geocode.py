"""Poner las ofertas en el mapa: de la ubicación escrita («Las Rozas de Madrid», «Arlington, VA») a un punto.

Se pregunta a Nominatim (el buscador de OpenStreetMap) por **el texto de cada ubicación distinta**, nunca por la oferta, la
empresa ni el perfil. Cumple su política de uso: una petición por segundo como máximo, un agente de usuario que identifica
la aplicación y los resultados (también los «no encontrado») se guardan en la base de datos para no repetir la pregunta.
Sin GTK.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from . import __version__

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = f"Grepleo/{__version__} (+https://github.com/seguidodoblado/grepleo)"
PAUSE_SECONDS = 1.1          # entre peticiones: su política permite una por segundo
TIMEOUT_SECONDS = 20

Coordinates = tuple[float, float]   # (latitud, longitud)


class GeocodeError(Exception):
    """Un fallo de red o de servicio: no se guarda como «no encontrado», se reintentará otra vez."""


class Geocoder:
    def __init__(self, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self._opener = opener

    def lookup(self, place: str) -> Coordinates | None:
        """El punto de un lugar, o None si Nominatim no lo conoce. Lanza `GeocodeError` si no se pudo preguntar."""
        query = urllib.parse.urlencode({"q": place, "format": "jsonv2", "limit": 1})
        request = urllib.request.Request(f"{NOMINATIM}?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with self._opener(request, timeout=TIMEOUT_SECONDS) as response:
                results = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as error:
            raise GeocodeError(f"Nominatim respondió con el error {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise GeocodeError(str(getattr(error, "reason", error))) from error
        if not isinstance(results, list) or not results:
            return None
        try:
            return float(results[0]["lat"]), float(results[0]["lon"])
        except (KeyError, TypeError, ValueError):
            return None


def geocode_places(places: list[str], geocoder: Geocoder, on_result: Callable[[str, Coordinates | None], None],
                   cancelled: Callable[[], bool] = lambda: False, pause: float = PAUSE_SECONDS,
                   sleep: Callable[[float], None] = time.sleep) -> str:
    """Pregunta por cada lugar, uno detrás de otro y con pausa, avisando de cada resultado con `on_result`. Se para al
    cancelarse o al primer fallo de red y devuelve su mensaje («» si terminó)."""
    for index, place in enumerate(places):
        if cancelled():
            return ""
        if index:
            sleep(pause)
        try:
            coordinates = geocoder.lookup(place)
        except GeocodeError as error:
            return str(error)
        on_result(place, coordinates)
    return ""


_REMOTE = re.compile(r"remot|teletrabaj|home\s*office|anywhere|internacional|international|cualquier", re.IGNORECASE)
_NOISE = re.compile(r"\b(ciudad|provincia|área|area|metropolitana|comunidad de|región|region)\b", re.IGNORECASE)


def clean_place(location: str) -> str:
    """El lugar que se pregunta a partir de la ubicación de una oferta: «Zaragoza Ciudad» → «Zaragoza», «Alicante/Alacant» →
    «Alicante». Vacío si no es un lugar («100% remoto», «International»): esas ofertas no van al mapa."""
    text = location.strip()
    if not text or _REMOTE.search(text):
        return ""
    text = _NOISE.sub(" ", text.split("/")[0])
    return re.sub(r"\s+", " ", text).strip(" ,-")
