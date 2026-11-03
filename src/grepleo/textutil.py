"""Utilidades de texto sin GTK: normalización, búsqueda de requisitos y datos que se deducen de una descripción."""
from __future__ import annotations

import re
import unicodedata

from .models import WorkMode


def normalize(text: str) -> str:
    """Minúsculas y sin acentos, para comparar sin que importen las tildes ni las mayúsculas."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def term_pattern(term: str) -> re.Pattern[str]:
    """Expresión que encuentra el término completo (no dentro de otra palabra) en un texto ya normalizado."""
    return re.compile(r"(?<!\w)" + re.escape(normalize(term).strip()) + r"(?!\w)")


def mentions(text_normalized: str, terms: list[str]) -> bool:
    return any(term_pattern(term).search(text_normalized) for term in terms if term.strip())


_YEARS_PATTERNS = (
    re.compile(r"(\d{1,2})\s*(?:a|-|–|y|to)\s*\d{1,2}\s*(?:anos?|years?)"),
    re.compile(r"(?:mas de|minimo de|minimo|al menos|at least|more than|over)\s*(\d{1,2})\+?\s*(?:anos?|years?)"),
    re.compile(r"(\d{1,2})\s*\+?\s*(?:anos?|years?)\s*(?:de|of)?\s*(?:experiencia|experience)"),
    re.compile(r"experiencia\s*(?:de|minima de|previa de)?\s*(\d{1,2})\+?\s*anos?"),
    re.compile(r"(\d{1,2})\+?\s*(?:anos?|years?)"),
)


def required_years(text: str) -> int | None:
    """Años de experiencia que pide el texto (el mínimo, si da un rango), o None si no dice nada."""
    normalized = normalize(text)
    if re.search(r"(?:sin|no se requiere|no requerid[ao]|no necesari[ao])\s*(?:\w+\s*)?experiencia", normalized):
        return 0
    for pattern in _YEARS_PATTERNS:
        for match in pattern.finditer(normalized):
            years = int(match.group(1))
            if 1 <= years <= 30:
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
