"""Cliente mínimo de la API de Apify (solo `urllib`): ejecutar un Actor y leer sus resultados."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from ..i18n import _

API = "https://api.apify.com/v2"
RUN_TIMEOUT_SECONDS = 300   # límite del endpoint síncrono de Apify


class ApifyError(Exception):
    """Fallo al hablar con Apify; el mensaje ya está en lenguaje de usuario."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _error_message(status: int, body: bytes) -> str:
    detail = ""
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        error = data.get("error") if isinstance(data, dict) else None
        detail = error.get("message", "") if isinstance(error, dict) else ""
    except ValueError:
        pass
    reasons = {
        401: _("El token de Apify no es válido."),
        402: _("Te has quedado sin crédito en Apify o el Actor requiere un plan de pago."),
        403: _("Apify no permite esta operación con tu token."),
        404: _("Apify no encuentra el Actor: puede haberse retirado o cambiado de nombre."),
        408: _("La búsqueda tardó demasiado y Apify la cortó."),
        429: _("Apify limita las peticiones: espera un poco y vuelve a intentarlo."),
    }
    message = reasons.get(status) or _("Apify respondió con el error {status}.").format(status=status)
    return f"{message} {detail}".strip() if detail else message


def _request(token: str, url: str, payload: dict[str, Any] | None, timeout: float,
             opener: Callable[..., Any]) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if payload is not None else "GET")
    request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with opener(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ApifyError(_error_message(error.code, error.read()), error.code) from error
    except urllib.error.URLError as error:
        raise ApifyError(_("No se pudo conectar con Apify: {reason}").format(reason=error.reason)) from error
    except (TimeoutError, OSError) as error:
        raise ApifyError(_("No se pudo conectar con Apify: {reason}").format(reason=error)) from error
    except ValueError as error:
        raise ApifyError(_("Apify devolvió una respuesta que no se entiende.")) from error


def run_actor(token: str, actor: str, actor_input: dict[str, Any], max_charge_usd: float,
              opener: Callable[..., Any] = urllib.request.urlopen) -> list[dict[str, Any]]:
    """Ejecuta un Actor y devuelve los elementos de su dataset. `max_charge_usd` es el tope de gasto de la
    ejecución: va como parámetro de la URL, no en la entrada del Actor, donde Apify no lo lee como tope."""
    query = urllib.parse.urlencode({"maxTotalChargeUsd": f"{max_charge_usd:.4f}", "timeout": RUN_TIMEOUT_SECONDS,
                                    "format": "json", "clean": "true"})
    url = f"{API}/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items?{query}"
    result = _request(token, url, actor_input, RUN_TIMEOUT_SECONDS + 30, opener)
    if not isinstance(result, list):
        raise ApifyError(_("Apify devolvió una respuesta que no se entiende."))
    return [item for item in result if isinstance(item, dict)]


def account_info(token: str, opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, str]:
    """Usuario y plan de la cuenta, para comprobar que el token funciona."""
    data = _request(token, f"{API}/users/me", None, 30, opener).get("data", {})
    return {"username": str(data.get("username", "")), "plan": str((data.get("plan") or {}).get("id", ""))}
