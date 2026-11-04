"""Michael Page España (consultora de selección), leída directamente de su web pública.

No usa Apify: pide las páginas de resultados y las fichas de michaelpage.es desde este equipo, con pausas y un
límite de ofertas por búsqueda, y por eso no cuesta nada. La web solo se consulta en las rutas que su `robots.txt`
permite (búsquedas y fichas). Cada ficha trae sus datos como JSON-LD (`JobPosting`) y, en el `dataLayer` de la
página, la banda salarial mínima del portal (40, 60, 80 mil…): no es un salario exacto, así que se muestra como
«desde X €» pero no se usa para puntuar el criterio de salario.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import __version__
from ..i18n import _
from ..models import Job, WorkMode
from ..textutil import detect_work_mode, normalize
from .base import SearchQuery, Source, SourceError, short_date, to_text

BASE = "https://www.michaelpage.es"
PAGE_SIZE = 30                 # ofertas por página de resultados
MAX_PAGES = 4                  # tope de páginas por búsqueda: la fuente es una web ajena, no se la recorre entera
TIMEOUT_SECONDS = 20
PAUSE_SECONDS = 0.4            # entre peticiones
WORKERS = 3                    # fichas pedidas a la vez
USER_AGENT = f"Grepleo/{__version__} (+https://github.com/seguidodoblado/grepleo)"
FULL_DESCRIPTION_CHARS = 150   # una descripción más corta es un resumen
_SINCE_DAYS = {"day": 1, "week": 7, "month": 30}

_TILE = re.compile(r'<li class="views-row">(.*?)(?=<li class="views-row">|</ul>)', re.DOTALL)
_HREF = re.compile(r'<h3><a href="(/job-detail/[^"?]+)"[^>]*>(.*?)</a>', re.DOTALL)
_LOGO = re.compile(r'<img[^>]*\balt="([^"]*?)(?: Logo)?"', re.DOTALL)
_LOCATION = re.compile(r'class="job-location">(?:<[^>]+>)*(.*?)</div>', re.DOTALL)
_CONTRACT = re.compile(r'class="job-contract-type">(?:<[^>]+>)*(.*?)</div>', re.DOTALL)
_SUMMARY = re.compile(r'class="job_advert__job-summary-text">(.*?)</div>', re.DOTALL)
_JSON_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
_SALARY = re.compile(r'"salary":\s*(\d+(?:\.\d+)?)\s*,\s*"salaryCurrency":\s*"([A-Z]*)"')


def html_to_text(fragment: str) -> str:
    """El HTML de una descripción como texto con saltos de línea y viñetas."""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</ul>", "\n", fragment)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in html.unescape(text).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse_listing(page: str) -> list[dict[str, Any]]:
    """Las ofertas de una página de resultados: título, enlace, ubicación, contrato y resumen."""
    tiles = []
    for block in _TILE.findall(page):
        link = _HREF.search(block)
        if not link:
            continue
        logo, location = _LOGO.search(block), _LOCATION.search(block)
        contract, summary = _CONTRACT.search(block), _SUMMARY.search(block)
        tiles.append({
            "url": BASE + html.unescape(link.group(1)), "title": html_to_text(link.group(2)),
            "company": html.unescape(logo.group(1)).strip() if logo else "",
            "location": html_to_text(location.group(1)) if location else "",
            "contract": html_to_text(contract.group(1)) if contract else "",
            "summary": html_to_text(summary.group(1)) if summary else ""})
    return tiles


def parse_detail(page: str) -> dict[str, Any]:
    """De una ficha: fecha, descripción completa, sector, modalidad declarada y salario (si lo publica)."""
    detail: dict[str, Any] = {}
    for raw in _JSON_LD.findall(page):
        try:
            data = json.loads(raw, strict=False)
        except ValueError:
            continue
        for entry in data if isinstance(data, list) else [data]:
            if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                address = (entry.get("jobLocation") or {}).get("address") or {}
                detail = {"posted": to_text(entry.get("datePosted")), "industry": to_text(entry.get("industry")),
                          "description": html_to_text(to_text(entry.get("description"))),
                          "telecommute": to_text(entry.get("jobLocationType")) == "TELECOMMUTE",
                          "locality": to_text(address.get("addressLocality"))}
                break
    salary = _SALARY.search(page)
    if salary and salary.group(2) in ("", "EUR") and float(salary.group(1)) > 0:
        detail["salary"] = float(salary.group(1))
    return detail


class _NotFound(SourceError):
    """404 de la web."""


class MichaelPage(Source):
    id = "michaelpage"
    name = "Michael Page"
    local = True

    def __init__(self, opener: Callable[..., Any] = urllib.request.urlopen,
                 pause: float = PAUSE_SECONDS) -> None:
        self._opener = opener
        self._pause = pause

    def _get(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es"})
        try:
            with self._opener(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise _NotFound from error
            raise SourceError(_("Michael Page respondió con el error {status}.").format(status=error.code)) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise SourceError(_("No se pudo conectar con Michael Page: {reason}").format(reason=reason)) from error

    def search_url(self, keywords: str, page: int) -> str:
        return f"{BASE}/jobs?" + urllib.parse.urlencode({"search": keywords, "page": page})

    def _listing(self, keywords: str, page: int) -> list[dict[str, Any]]:
        try:
            return parse_listing(self._get(self.search_url(keywords, page)))
        except _NotFound:
            return []   # la web responde 404 cuando una búsqueda no tiene ninguna oferta

    def fetch(self, query: SearchQuery) -> list[dict[str, Any]]:
        # La web exige todas las palabras a la vez: una lista separada por comas son búsquedas distintas.
        terms = [term.strip() for term in query.keywords.split(",") if term.strip()] or [query.keywords]
        pages = min(MAX_PAGES, max(1, -(-query.limit // PAGE_SIZE) + 1))   # algo más de lo pedido: se filtra después
        tiles: list[dict[str, Any]] = []
        seen: set[str] = set()
        first = True
        for term in terms:
            for number in range(pages):
                if not first:
                    time.sleep(self._pause)
                first = False
                found = [tile for tile in self._listing(term, number) if tile["url"] not in seen]
                seen.update(tile["url"] for tile in found)
                tiles.extend(found)
                if len(found) < PAGE_SIZE or len(tiles) >= query.limit * 2:
                    break
        tiles = [tile for tile in tiles if self._wanted_place(tile["location"], query)][:query.limit]
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            details = list(pool.map(self._detail, tiles))
        items = [{**tile, **detail} for tile, detail in zip(tiles, details, strict=True)]
        return [item for item in items if self._recent_enough(item.get("posted", ""), query.posted)]

    def _detail(self, tile: dict[str, Any]) -> dict[str, Any]:
        time.sleep(self._pause)
        try:
            return parse_detail(self._get(tile["url"]))
        except SourceError:
            return {}   # sin ficha se conserva el resumen del listado, marcado como ficha resumida

    @staticmethod
    def _wanted_place(location: str, query: SearchQuery) -> bool:
        """La web no filtra por ciudad con texto libre: se filtra aquí (las ofertas remotas se conservan)."""
        wanted = normalize(query.location)
        if not wanted:
            return True
        place = normalize(location)
        return wanted in place or "remot" in place or (query.remote and not place)

    @staticmethod
    def _recent_enough(posted: str, window: str) -> bool:
        days = _SINCE_DAYS.get(window)
        if not days or not posted:
            return True
        try:
            date = datetime.fromisoformat(posted[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            return True
        return date >= datetime.now(timezone.utc) - timedelta(days=days + 1)

    def build_input(self, query: SearchQuery) -> dict[str, Any]:
        return {"search": query.keywords, "page": 0}   # no hay Actor: es la consulta a la web

    def parse_item(self, item: dict[str, Any]) -> Job | None:
        url, title = to_text(item.get("url")), to_text(item.get("title"))
        reference = url.rsplit("/ref/", 1)[-1] if "/ref/" in url else url
        if not reference or not title:
            return None
        text = to_text(item.get("description")) or to_text(item.get("summary"))
        band = item.get("salary")
        floor = float(band) if isinstance(band, (int, float)) and not isinstance(band, bool) and band > 0 else 0.0
        mode = detect_work_mode(f"{title} {text}")
        if mode is WorkMode.UNKNOWN and item.get("telecommute"):
            mode = WorkMode.REMOTE
        return Job(
            key=f"{self.id}:{reference}", source=self.id, title=title,
            company=to_text(item.get("company")) or "Michael Page",
            location=to_text(item.get("location")) or to_text(item.get("locality")), work_mode=mode,
            contract=to_text(item.get("contract")),
            salary_text=_("desde {amount} €").format(amount=f"{floor:,.0f}".replace(",", ".")) if floor else "",
            description=text,
            full_description=bool(item.get("description")) and len(text) >= FULL_DESCRIPTION_CHARS,
            url=url, posted=short_date(item.get("posted")))
