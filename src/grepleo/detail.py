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
what you will do|what you'll do|benefits|skills|description|job description|here's what you need|what you need
what you bring|your profile|key responsibilities|required qualifications|preferred qualifications
minimum qualifications|role requirements|must have|why join us|tasks and responsibilities|goals & objectives
summary|overview|job summary|role overview|position summary|purpose of position|the role|your role|about you
tu perfil|tus responsabilidades|que necesitas|lo que necesitas|lo que aportas|que aportas|que te ofrecemos
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


# palabras técnicas escritas con mayúscula en medio: no son dos frases pegadas
_CAMEL_WORDS = frozenset(["JavaScript", "TypeScript", "DevOps", "DevSecOps", "GitHub", "GitLab", "PowerShell", "OpenShift", "CloudFormation", "CloudWatch", "SonarQube", "ServiceNow", "SharePoint", "PowerPoint", "OneDrive", "WordPress", "HashiCorp", "LinkedIn", "YouTube", "FinOps", "MLOps", "AIOps", "DataDog", "ElasticSearch", "SageMaker", "BitBucket", "TeamCity", "LangChain", "HuggingFace", "OpenStack", "OpenTelemetry", "PagerDuty", "SpringBoot", "NodeJs", "ReactJs", "VueJs", "AngularJs", "DevEx", "McKinsey", "PayPal", "FedEx"])
_CAMEL = re.compile(r"(?<=[a-z]{2})(?=[A-Z][a-z])|(?<=[A-Z]{2})(?=[A-Z][a-z]{3})|(?<=[)\]])(?=[A-Z][a-z])")
_PROTECTED = re.compile("|".join(sorted(_CAMEL_WORDS, key=len, reverse=True)))
_MIN_LIST_BREAKS = 3    # con menos cortes que esto no es una lista pegada, sino un nombre propio con mayúscula en medio
_GLUED_SENTENCE = re.compile(r"(?<=[a-z0-9)\]])([.!?])(?=[A-Z¿¡])")   # «mission.What»: dos frases sin espacio
_GLUED_COLON = re.compile(r"(?<=[a-z)])(:)(?=[A-Z¿¡])")           # «Strategy:Work»
_INLINE_HEADING = re.compile(r"^(.{3,50}?):\s+(?=\S)")
_FLAT_LINE = 300       # una línea más larga que esto sin saltos es texto aplastado (LinkedIn quita los saltos)
_SHORT_WORDS = 7


def _protect_camel(line: str) -> list[str]:
    """Trocea una línea por los sitios donde dos elementos se pegaron sin separador, respetando JavaScript, DevOps…"""
    protected = [match.span() for match in _PROTECTED.finditer(line)]
    parts, last = [], 0
    for match in _CAMEL.finditer(line):
        mark = match.start()
        if any(start < mark < end for start, end in protected):
            continue
        parts.append(line[last:mark])
        last = mark
    parts.append(line[last:])
    return [part for part in parts if part.strip()]


def _explode_flat(text: str) -> str:
    """Devuelve con saltos de línea el texto al que se le quitaron: frases y elementos de lista pegados.

    Solo toca las líneas largas sin saltos (el texto de LinkedIn llega así). Una frase que acaba en punto y sigue sin
    espacio es un párrafo nuevo; dos palabras pegadas con mayúscula en medio son dos elementos (viñetas), salvo que
    el primero sea un título corto («SummaryWe are…»)."""
    out: list[str] = []
    for line in text.replace("\r", "").split("\n"):
        if len(line) < _FLAT_LINE:
            out.append(line)
            continue
        line = _GLUED_SENTENCE.sub(lambda m: m.group(1) + "\n\n", line)
        line = _GLUED_COLON.sub(lambda m: m.group(1) + "\n", line)
        for piece in line.split("\n"):
            segments = _protect_camel(piece) if piece.strip() else [piece]
            if len(segments) <= 1:
                out.append(piece)
                continue
            first = segments[0]
            if len(first.split()) <= _SHORT_WORDS and first.rstrip()[-1:] not in _TERMINAL and len(segments[1].split()) >= 6:
                out.append(f"## {first.strip()}")   # título pegado al texto que le sigue
                segments = segments[1:]
            if len(segments) > _MIN_LIST_BREAKS:
                out.extend(f"## {segment.strip()}" if normalize(segment).strip(" :") in _HEADINGS
                           else f"- {segment.strip()}" for segment in segments)
            else:
                out.append(" ".join(segment.strip() for segment in segments))
    return "\n".join(out)


def _heading_text(line: str) -> str:
    return _clean(line.strip().removeprefix("## ")).rstrip(":").strip()


def _is_title_like(line: str, following: str) -> bool:
    """Una línea corta, sin punto y con una más larga detrás, dentro de un grupo: «Funciones principales»."""
    stripped = line.strip()
    words = stripped.split()
    return (0 < len(words) <= _SHORT_WORDS and len(stripped) <= 50 and stripped[-1] not in _TERMINAL + ","
            and stripped[0].isupper() and not _MARKER.match(stripped) and len(following.strip()) >= len(stripped) * 1.3
            and (len(following.strip()) >= 40 or (len(following.strip()) >= 20 and following.strip()[-1] in _TERMINAL)))


def _items_to_blocks(run: list[str]) -> list[Block]:
    """Las líneas seguidas de una sección como viñetas (si hay varias elementos) o como un párrafo."""
    marked = any(_MARKER.match(line) for line in run)
    items: list[str] = []
    for line in run:
        clean = _clean(line)
        if not clean:
            continue
        continues = (items and not marked and items[-1][-1] not in _TERMINAL
                     and (clean[0].islower() or items[-1][-1] == ","))
        if continues:
            items[-1] += " " + clean
        else:
            items.append(clean)
    if marked or len(items) >= 2:
        return [Block(BULLET, item) for item in items]
    return [Block(PARAGRAPH, items[0])] if items else []


def structure_description(text: str) -> list[Block]:
    """Parte el texto en títulos, viñetas y párrafos.

    Respeta lo que trae (marcas de lista, líneas en blanco) y, sin marcas, toma como viñetas las líneas sueltas que
    empiezan por mayúscula tras otra que no deja la frase a medias; un párrafo cortado a mano en líneas se vuelve a
    unir. Un título (conocido, con dos puntos o corto y sin punto) abre una sección aunque no vaya tras una línea en
    blanco. El texto aplastado en una sola línea se trocea antes (ver `_explode_flat`).
    """
    blocks: list[Block] = []
    for group in re.split(r"\n\s*\n", _explode_flat(text)):
        lines = [line for line in group.split("\n") if line.strip()]
        run: list[str] = []
        for index, line in enumerate(lines):
            following = lines[index + 1] if index + 1 < len(lines) else ""
            title = line.startswith("## ") or _is_heading(line) or (
                index > 0 and not _MARKER.match(line) and _is_title_like(line, following))
            if title and not (index == 0 and len(lines) == 1 and not line.startswith("## ") and not _is_heading(line)):
                blocks.extend(_items_to_blocks(run))
                run = []
                blocks.append(Block(HEADING, _heading_text(line)))
                continue
            plain = _clean(line)
            inline = _INLINE_HEADING.match(plain)
            if inline and normalize(inline.group(1)).strip(" *#_-") in _HEADINGS:
                blocks.extend(_items_to_blocks(run))
                blocks.append(Block(HEADING, inline.group(1).strip()))
                run = [f"- {plain[inline.end():]}" if _MARKER.match(line) else plain[inline.end():]]
                continue
            run.append(line)
        blocks.extend(_items_to_blocks(run))
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
