"""Token de Apify en el llavero del sistema (libsecret), nunca en un archivo."""
from __future__ import annotations

import keyring
import keyring.errors

_SERVICE = "grepleo"
_USER = "apify_token"


class SecretsError(Exception):
    """No hay un llavero utilizable en este equipo."""


def get_token() -> str | None:
    try:
        return keyring.get_password(_SERVICE, _USER) or None
    except keyring.errors.KeyringError as error:
        raise SecretsError(str(error)) from error


def set_token(token: str) -> None:
    token = token.strip()
    try:
        if token:
            keyring.set_password(_SERVICE, _USER, token)
        else:
            clear_token()
    except keyring.errors.KeyringError as error:
        raise SecretsError(str(error)) from error


def clear_token() -> None:
    try:
        keyring.delete_password(_SERVICE, _USER)
    except keyring.errors.PasswordDeleteError:
        pass   # ya no había token
    except keyring.errors.KeyringError as error:
        raise SecretsError(str(error)) from error
