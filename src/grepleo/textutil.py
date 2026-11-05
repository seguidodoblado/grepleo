"""Utilidades de texto sin GTK: normalización, búsqueda de requisitos y datos que se deducen de una descripción."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .models import WorkMode

_COMBINING = re.compile("[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]")   # las marcas de acento


@lru_cache(maxsize=1024)
def normalize(text: str) -> str:
    """Minúsculas y sin acentos, para comparar sin que importen las tildes ni las mayúsculas."""
    folded = text.casefold()
    if folded.isascii():
        return folded
    return _COMBINING.sub("", unicodedata.normalize("NFKD", folded))


@lru_cache(maxsize=4096)
def term_pattern(term: str) -> re.Pattern[str]:
    """Expresión que encuentra el término completo (no dentro de otra palabra) en un texto ya normalizado."""
    return re.compile(r"(?<!\w)" + re.escape(normalize(term).strip()) + r"(?!\w)")


@lru_cache(maxsize=4096)
def _needle(term: str) -> str:
    return normalize(term).strip()


def mentions(text_normalized: str, terms: list[str]) -> bool:
    # buscar antes el texto literal (rapidísimo) y solo si está, comprobar que es una palabra completa
    return any(_needle(term) in text_normalized and term_pattern(term).search(text_normalized)
               for term in terms if term.strip())


_YEARS_PATTERNS = (
    re.compile(r"(\d{1,2})\s*(?:a|-|–|y|to)\s*\d{1,2}\s*(?:anos?|years?)"),
    re.compile(r"(?:mas de|minimo de|minimo|al menos|at least|more than|over)\s*(\d{1,2})\+?\s*(?:anos?|years?)"),
    re.compile(r"(\d{1,2})\s*\+?\s*(?:anos?|years?)\s*(?:de|of)?\s*(?:experiencia|experience)"),
    re.compile(r"experiencia\s*(?:de|minima de|previa de)?\s*(\d{1,2})\+?\s*anos?"),
    re.compile(r"(\d{1,2})\+?\s*(?:anos?|years?)"),
)


# lo que antecede a una cifra de años cuando es un tope o una edad, no un mínimo de experiencia
_NOT_A_MINIMUM_BEFORE = re.compile(
    r"(?:hasta|maximo|menos de|no tener|no superar|no mas de|menor(?:es)? de|mayor(?:es)? de|edad de|edad)\s*(?:\w+\s*){0,3}$")
_AGE_AFTER = re.compile(r"^\s*(?:de edad|cumplidos)")
_EXPERIENCE_WORD = re.compile(r"experiencia|experience")
_SENTENCE_END = re.compile(r"[.;!?\n]")


def _sentence_around(text: str, start: int, end: int) -> str:
    """La frase (hasta el punto, punto y coma o salto de línea más cercano) que contiene text[start:end]."""
    before = [m.end() for m in _SENTENCE_END.finditer(text, 0, start)]
    after = _SENTENCE_END.search(text, end)
    return text[(before[-1] if before else 0):(after.start() if after else len(text))]


def required_years(text: str, strict: bool = False) -> int | None:
    """Años de experiencia que pide el texto (el mínimo, si da un rango), o None si no dice nada.

    Con `strict` (para una descripción larga, no un campo corto como «Al menos 3 años») solo vale una cifra que
    tenga «experiencia» en su misma frase: así no se confunden con la experiencia una edad ni la antigüedad de una empresa.
    """
    normalized = normalize(text)
    if re.search(r"(?:sin|no se requiere|no requerid[ao]|no necesari[ao])\s*(?:\w+\s*)?experiencia", normalized):
        return 0
    for pattern in _YEARS_PATTERNS:
        for match in pattern.finditer(normalized):
            years = int(match.group(1))
            if not 1 <= years <= 30:
                continue
            if _NOT_A_MINIMUM_BEFORE.search(normalized[max(0, match.start() - 30):match.start()]):
                continue
            if _AGE_AFTER.match(normalized[match.end():match.end() + 15]):
                continue
            if strict and not _EXPERIENCE_WORD.search(_sentence_around(normalized, match.start(), match.end())):
                continue
            return years
    return None


_STUDIES_LEVELS = (
    (3, re.compile(r"master|posgrado|postgrado|doctorado")),
    (2, re.compile(r"grado|licenciatura|ingenier|diplomatura|universitari|degree|bachelor")),
    (1, re.compile(r"\bfp\b|ciclo formativo|formacion profesional|vocational")),
)


def studies_rank(text: str) -> int | None:
    """Nivel de estudios que cita un texto: 1 FP, 2 grado, 3 máster; None si no cita ninguno."""
    # «Grado superior» y «grado medio» son de FP, no un grado universitario
    normalized = re.sub(r"ciclos? formativos? de grado (?:superior|medio)|grado (?:superior|medio)", "fp",
                        normalize(text))
    for rank, pattern in _STUDIES_LEVELS:
        if pattern.search(normalized):
            return rank
    return None


_STUDIES_CONTEXT = re.compile(
    r"titulacion|titulad|estudios|formacion (?:academica|universitaria|reglada)|licenciatura|licenciad|grado en"
    r"|master|ciclo formativo|\bfp\b|degree|bachelor|diplomatura")


def studies_in_description(text: str) -> tuple[int | None, str]:
    """Nivel de estudios y la frase que lo pide, mirando solo las frases que hablan de titulación o estudios.

    Una descripción cita «ingeniero» o «grado» por otros motivos (el título del puesto, «un alto grado de
    autonomía»); por eso, a diferencia de un campo de estudios del portal, no se lee entera.
    """
    for sentence in re.split(r"[.;!?\n]", text):
        if _STUDIES_CONTEXT.search(normalize(sentence)):
            rank = studies_rank(sentence)
            if rank is not None:
                return rank, " ".join(sentence.split())[:120]
    return None, ""


_LANGUAGES = {
    "Inglés": ("ingles", "english"),
    "Francés": ("frances", "french"),
    "Alemán": ("aleman", "german"),
    "Portugués": ("portugues", "portuguese"),
    "Italiano": ("italiano", "italian"),
    "Catalán": ("catalan", "catala"),
    "Euskera": ("euskera", "basque"),
}
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
_LEVEL_WORDS = (("c2", r"nativo|native|bilingue"), ("c1", r"avanzado|fluido|fluent|advanced"),
                ("b2", r"intermedio alto|upper.?intermediate"), ("b1", r"intermedio|intermediate"))


def level_rank(level: str) -> int:
    """Posición de un nivel MCER en la escala (0 si no se reconoce)."""
    level = level.strip().upper()
    return LEVELS.index(level) + 1 if level in LEVELS else 0


def _clause(text: str, start: int, end: int) -> str:
    """La frase (entre signos de puntuación) que contiene una coincidencia: el nivel que lleva es el suyo."""
    before = max((m.end() for m in re.finditer(r"[.;,\n]", text[:start])), default=0)
    after = re.search(r"[.;,\n]", text[end:])
    return text[before: end + after.start() if after else len(text)]


def language_requirements(text: str) -> dict[str, str]:
    """Idiomas que menciona el texto, con el nivel MCER si lo dice cerca: {«Inglés»: «C1»}. Sin nivel, «»."""
    normalized = normalize(text)
    found: dict[str, str] = {}
    for name, words in _LANGUAGES.items():
        level = ""
        mentioned = False
        for match in re.finditer(r"(?<!\w)(?:" + "|".join(words) + r")(?!\w)", normalized):
            mentioned = True
            window = _clause(normalized, match.start(), match.end())
            if found_level := re.search(r"(?<!\w)([abc][12])(?!\w)", window):
                level = found_level.group(1).upper()
                break
            for candidate, words_pattern in _LEVEL_WORDS:
                if re.search(words_pattern, window):
                    level = candidate.upper()
                    break
        if mentioned:
            found[name] = level
    return found


def detect_work_mode(text: str) -> WorkMode:
    """Modalidad que dice el texto: remoto, híbrido o presencial; desconocida si no dice nada."""
    normalized = normalize(text)
    if re.search(r"hibrid|hybrid|(\d)\s*dias? (?:de )?(?:teletrabajo|presencial|en oficina)", normalized):
        return WorkMode.HYBRID
    if re.search(r"100\s*%\s*remot|full.?remote|totalmente remot|remote|remoto|teletrabajo|trabajo en remoto",
                 normalized):
        return WorkMode.REMOTE
    if re.search(r"presencial|on.?site|in.?office", normalized):
        return WorkMode.ONSITE
    return WorkMode.UNKNOWN
