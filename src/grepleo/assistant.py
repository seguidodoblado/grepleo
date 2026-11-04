"""Asistente de IA en un terminal: lanza la CLI que ya tienes instalada (Claude Code, OpenCode, Codex…) con un mensaje
definido para adaptar tu currículum a una oferta.

La aplicación no toca credenciales ni llama a ninguna API: tú usas tu propia sesión en el terminal. Cada oferta tiene su
carpeta de trabajo con solo lo necesario (la oferta, tu CV base y, si lo hay, tu CV subido), así la sesión no ve tus
proyectos. Sin GTK.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .ats import estimate_ats
from .cv import offer_markdown, profile_markdown
from .i18n import _
from .models import Evaluation, Job
from .profiles import Profile

DEFAULT_COMMAND = "claude {prompt}"
OUTPUT_NAME = "cv-adaptado.md"
PROMPT = ("Adapta mi currículum a la oferta de empleo que tienes en @{offer}, que incluye la descripción y qué "
          "criterios de la oferta cumplo según mi perfil. Mi currículum base, construido desde mi perfil, está en "
          "@{cv}.{upload} "
          "Escribe el resultado en el archivo {output} (Markdown, en una sola columna, sin tablas ni imágenes) con "
          "estas secciones estándar para que los filtros ATS lo lean bien: Resumen, Experiencia profesional, "
          "Formación, Idiomas y Habilidades. "
          "Reglas: no inventes experiencia, empresas, fechas, títulos, cifras ni tecnologías que no estén en mis "
          "datos; reordena y reformula lo que sí tengo para destacar lo que pide la oferta; usa sus palabras clave "
          "(en oferta.md figuran las que mi CV base no cita) solo cuando sean ciertas en mi caso; escribe en el idioma de la oferta y que quepa en dos páginas. "
          "Al terminar, dime en pocas líneas qué has destacado y qué requisitos de la oferta no puedo cubrir con "
          "mis datos. No toques ningún otro archivo.")


def build_prompt(template: str, offer: str, cv: str, upload: str = "", output: str = OUTPUT_NAME) -> str:
    """El mensaje para el asistente: `template` (el editable de Preferencias o el de serie) con los nombres de archivo
    ya sustituidos. `{upload}` pasa a ser una frase sobre tu CV subido, o nada si no lo hay."""
    note = (" " + _("También tienes mi currículum original en @{name}: úsalo como fuente principal si puedes leerlo.")
            .format(name=upload)) if upload else ""
    text = (template.strip() or PROMPT)
    for placeholder, value in (("{upload}", note), ("{offer}", offer), ("{cv}", cv), ("{output}", output)):
        text = text.replace(placeholder, value)
    return text


def build_argv(template: str, prompt: str) -> list[str]:
    """Trocea la plantilla del comando y sustituye `{prompt}`; lanza ValueError si está vacía o mal formada."""
    tokens = shlex.split(template)
    if not tokens:
        raise ValueError(_("El comando del asistente está vacío."))
    return [prompt if token == "{prompt}" else token for token in tokens]


def shell_argv(argv: list[str]) -> list[str]:
    """Lanza `argv` desde tu shell interactiva: así encuentra las CLIs que solo están en el PATH de tu ~/.bashrc
    (opencode en ~/.opencode/bin, codex bajo nvm…), que una app lanzada desde el menú no ve."""
    shell = os.environ.get("SHELL") or "/bin/bash"
    return [shell, "-ic", "exec " + shlex.join(argv)]


@dataclass
class Workspace:
    folder: Path
    offer: str       # nombres de archivo dentro de la carpeta
    cv: str
    upload: str
    output: str


def folder_name(job_key: str) -> str:
    """Un nombre de carpeta seguro para la clave de una oferta («infojobs:abc» → «infojobs-abc»)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", job_key).strip("-.")[:80] or "oferta"


def prepare_workspace(base: Path, job: Job, evaluation: Evaluation, profile: Profile) -> Workspace:
    """Deja en la carpeta de la oferta lo que el asistente necesita (se rehace cada vez) y aparta el CV adaptado de la
    vez anterior para no pisarlo."""
    folder = base / folder_name(job.key)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "oferta.md").write_text(offer_markdown(job, evaluation, estimate_ats(job, profile)), encoding="utf-8")
    (folder / "cv-base.md").write_text(profile_markdown(profile), encoding="utf-8")
    for old in folder.glob("cv-subido.*"):
        old.unlink()
    upload = ""
    source = Path(profile.cv_file) if profile.cv_file else None
    if source is not None and source.is_file():
        upload = f"cv-subido{source.suffix.lower()}"
        shutil.copyfile(source, folder / upload)
    previous = folder / OUTPUT_NAME
    if previous.exists():
        stamp = datetime.fromtimestamp(previous.stat().st_mtime, timezone.utc).strftime("%Y%m%d-%H%M%S")
        previous.rename(folder / f"cv-adaptado-{stamp}.md")
    return Workspace(folder, "oferta.md", "cv-base.md", upload, OUTPUT_NAME)
