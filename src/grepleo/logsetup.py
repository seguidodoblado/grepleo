"""Registro de errores: lo que Grepleo escribe en la salida de errores (excepciones de Python, avisos de GTK) se guarda en
`~/.local/share/grepleo/grepleo.log`. Lanzada desde el menú, esa salida iría a /dev/null y un fallo no dejaría rastro.

Con `kill -USR1 <pid>` un proceso colgado vuelca en el registro lo que hace cada hilo. Sin GTK.
"""
from __future__ import annotations

import faulthandler
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

from . import __version__

_handle = None   # el archivo abierto: tiene que vivir todo el proceso (faulthandler usa su descriptor)
MAX_BYTES = 1_000_000   # por encima, el registro anterior pasa a «.1» (solo se guarda uno)


def log_path() -> Path:
    from .storage import DATA_DIR
    return DATA_DIR / "grepleo.log"


def install(path: Path | None = None, redirect: bool | None = None) -> Path | None:
    """Abre el registro, enlaza la salida de errores con él (salvo que haya un terminal) y activa el volcado de
    hilos con SIGUSR1 y ante fallos graves. Devuelve la ruta, o None si no se pudo escribir (no es motivo para no arrancar)."""
    target = path or log_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size > MAX_BYTES:
            target.replace(target.with_suffix(".log.1"))
        handle = open(target, "a", buffering=1, encoding="utf-8")   # noqa: SIM115 - vive todo el proceso
    except OSError:
        return None
    global _handle
    _handle = handle
    handle.write(f"--- {datetime.now().astimezone().isoformat(timespec='seconds')} Grepleo {__version__} "
                 f"(pid {os.getpid()})\n")
    if redirect is None:
        redirect = not os.isatty(2)   # desde un terminal, los errores se siguen viendo en él
    if redirect:
        os.dup2(handle.fileno(), 2)
        sys.stderr = open(2, "w", buffering=1, encoding="utf-8", closefd=False)  # noqa: SIM115
    faulthandler.enable(file=handle, all_threads=True)
    try:
        faulthandler.register(signal.SIGUSR1, file=handle, all_threads=True)
    except (AttributeError, ValueError, OSError):
        pass   # sin SIGUSR1 en esta plataforma
    return target
