"""El texto de una oferta preparado para leerse: secciones, viñetas y lo que de tu perfil aparece en él.

Sin GTK: la ventana solo dibuja lo que se calcula aquí, y así se puede probar.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .profiles import parse_term
from .textutil import normalize, term_pattern

HEADING, BULLET, PARAGRAPH = "heading", "bullet", "paragraph"
GOOD, BAD = "good", "bad"

# encabezados habituales (normalizados, sin los dos puntos finales)
_HEADINGS = frozenset("""
descripcion|descripcion del puesto|descripcion de la oferta|sobre el puesto|el puesto|el rol|que buscamos
lo que buscamos|buscamos|requisitos|requisitos minimos|requisitos tecnicos|requisitos deseables|requisitos del puesto
se valorara|se valora|valorable|deseable|deseables|se valorara positivamente|funciones|responsabilidades
principales funciones|tus funciones|lo que haras|que haras|tareas|que ofrecemos|lo que ofrecemos|ofrecemos|te ofrecemos
beneficios|condiciones|que te ofrecemos|sobre nosotros|sobre la empresa|quienes somos|conocimientos|formacion
experiencia|requirements|responsibilities|qualifications|what we offer|we offer|nice to have|about us|about the role
what you will do|what you'll do|benefits|skills|description|job description
""".replace("\n", "|").split("|")) - {""}
_MARKER = re.compile(r"^\s*(?:[-–—•·▪●◦*►>]+|\d{1,2}[.)])\s+")
_TERMINAL = ".;:!?"
_MAX_HEADING = 70


@dataclass
class Block:
    kind: str
    text: str


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING:
        return False
    key = normalize(stripped).rstrip(" :").strip(" *#_-")
    return key in _HEADINGS or (stripped.endswith(":") and len(stripped) <= 50 and not _MARKER.match(stripped))


def _clean(line: str) -> str:
    return " ".join(_MARKER.sub("", line, count=1).split())


def structure_description(text: str) -> list[Block]:
    """Parte el texto en títulos, viñetas y párrafos.

    Respeta lo que trae (marcas de lista, líneas en blanco) y, sin marcas, toma como viñetas las líneas sueltas que
    terminan en punto o parecidas; un párrafo cortado a mano en líneas largas se vuelve a unir.
    """
    blocks: list[Block] = []
    for group in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = [line for line in group.split("\n") if line.strip()]
        if not lines:
            continue
        if _is_heading(lines[0]):
            blocks.append(Block(HEADING, _clean(lines[0]).rstrip(":").strip()))
            lines = lines[1:]
        if not lines:
            continue
        marked = [bool(_MARKER.match(line)) for line in lines]
        ends = sum(1 for line in lines if line.rstrip()[-1] in _TERMINAL)
        if any(marked) or (len(lines) >= 2 and ends * 2 >= len(lines)):
            # cada línea es un elemento; una sin marca tras una con marca sigue siendo uno aparte
            blocks.extend(Block(BULLET, _clean(line)) for line in lines if _clean(line))
        else:
            blocks.append(Block(PARAGRAPH, _clean(" ".join(lines))))
    return blocks


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """El texto normalizado y, por cada uno de sus caracteres, la posición del original de la que sale."""
    out: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        piece = "".join(c for c in unicodedata.normalize("NFKD", char.casefold()) if not unicodedata.combining(c))
        out.append(piece)
        origin.extend([index] * len(piece))
    return "".join(out), origin


def highlight_spans(text: str, good: list[str], bad: list[str]) -> list[tuple[int, int, str]]:
    """Dónde aparecen en `text` los términos que se buscan (`good`) y los que se prefiere evitar (`bad`).

    Cada término puede traer sinónimos con «|». Devuelve (inicio, fin, GOOD o BAD) sobre el texto original, ordenado
    y sin solapes: si dos coinciden, gana la que empieza antes (y, a igual inicio, la más larga).
    """
    normalized, origin = _normalize_with_map(text)
    found: list[tuple[int, int, str]] = []
    for kind, specs in ((GOOD, good), (BAD, bad)):
        for spec in specs:
            for name in parse_term(spec)[1]:
                if not name.strip():
                    continue
                for match in term_pattern(name).finditer(normalized):
                    if match.end() > match.start():
                        found.append((origin[match.start()], origin[match.end() - 1] + 1, kind))
    found.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    spans: list[tuple[int, int, str]] = []
    for start, end, kind in found:
        if not spans or start >= spans[-1][1]:
            spans.append((start, end, kind))
    return spans
