"""Currículum: el CV base que se construye desde el perfil, la oferta como texto y la conversión a HTML. Sin GTK."""
from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

from .i18n import _
from .links import profile_links
from .models import Evaluation, Job, Status
from .profiles import Profile, parse_term


def _group_titles() -> tuple[tuple[str, str], ...]:
    return (("hard", _("Habilidades técnicas")), ("soft", _("Habilidades blandas")), ("conditions", _("Condiciones")))


def _studies_label(key: str) -> str:
    return {"fp": _("Formación Profesional"), "degree": _("Grado universitario"), "master": _("Máster")}.get(key, "")


def _names(specs: list[str]) -> list[str]:
    return [name for spec in specs if (name := parse_term(spec)[0])]


def profile_markdown(profile: Profile) -> str:
    """El currículum base: todo lo que el perfil sabe de ti, ordenado como lo esperan los filtros ATS (una columna,
    títulos estándar y sin tablas). La IA lo toma como la única fuente de verdad: no se inventa nada más."""
    lines = [f"# {profile.full_name or profile.name}"]
    contact = [part for part in (profile.email, profile.phone) if part]
    if contact:
        lines.append(" · ".join(contact))
    links = profile_links(profile)
    if links:   # en una sola línea, separados por « · »: es lo que los filtros ATS leen mejor
        lines.append(" · ".join(links))
    summary = profile.headline.strip()
    if profile.years:
        years = _("{count} años de experiencia").format(count=profile.years)
        summary = f"{summary}. {years}" if summary else years
    if summary:
        lines += ["", f"## {_('Resumen')}", summary]
    if profile.experience.strip():
        lines += ["", f"## {_('Experiencia profesional')}", profile.experience.strip()]
    education = [item for item in (_studies_label(profile.studies), profile.education.strip()) if item]
    if education:
        lines += ["", f"## {_('Formación')}", *education]
    if profile.languages:
        lines += ["", f"## {_('Idiomas')}", *(f"- {language} ({level})" for language, level in profile.languages.items())]
    technical = [*_names(profile.must), *_names(profile.nice)]
    if technical:
        lines += ["", f"## {_('Habilidades técnicas')}", ", ".join(dict.fromkeys(technical))]
    soft = [*_names(profile.soft_must), *_names(profile.soft_nice)]
    if soft:
        lines += ["", f"## {_('Habilidades blandas')}", ", ".join(dict.fromkeys(soft))]
    return "\n".join(lines) + "\n"


_MAX_UPLOAD_BYTES = 4_000_000


def uploaded_cv_text(profile: Profile) -> str:
    """El texto del CV que has subido, si se puede leer sin herramientas externas: texto plano, Markdown, Word (.docx) y
    OpenDocument (.odt). Un PDF no se lee aquí (devuelve ''): para la estimación se usa tu CV base."""
    if not profile.cv_file:
        return ""
    path = Path(profile.cv_file)
    try:
        if not path.is_file() or path.stat().st_size > _MAX_UPLOAD_BYTES:
            return ""
        suffix = path.suffix.lower()
        if suffix in (".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="replace")
        member = {".docx": "word/document.xml", ".odt": "content.xml"}.get(suffix)
        if member:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read(member).decode("utf-8", errors="replace")
            xml = re.sub(r"</(?:w:p|text:p|text:h)>", "\n", xml)
            return html.unescape(re.sub(r"<[^>]+>", " ", xml))
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    return ""


def offer_markdown(job: Job, evaluation: Evaluation, ats=None) -> str:
    """La oferta y cómo encaja tu perfil con ella, para que la IA sepa qué destacar y qué falta."""
    facts = [job.company, job.location, job.work_mode.label if job.work_mode.value != "unknown" else "",
             job.contract, job.salary_text]
    lines = [f"# {job.title}", " · ".join(fact for fact in facts if fact)]
    if job.url:
        lines.append(job.url)
    if job.posted:
        lines.append(_("Publicada el {date}").format(date=job.posted))
    lines += ["", f"## {_('Descripción')}", job.description.strip() or _("(La fuente solo da una ficha resumida.)"),
              "", f"## {_('Encaje con mi perfil (evaluación local)')}", _("Encaje: {fit}").format(fit=evaluation.fit.label)]
    symbols = {Status.MET: "✓", Status.MISSING: "✗", Status.UNKNOWN: "?"}
    for group, title in _group_titles():
        items = [item for item in evaluation.criteria if item.group == group]
        if items:
            lines += ["", f"### {title}"]
            for item in items:
                required = f" ({_('imprescindible')})" if item.required and item.status is Status.MISSING else ""
                lines.append(f"- {symbols[item.status]} {item.name}{required}" + (f": {item.detail}" if item.detail else ""))
    if ats is not None:
        lines += ["", f"## {_('Estimación ATS de mi CV base')}",
                  _("Compatibilidad estimada: {percent} %").format(percent=ats.percent)]
        if ats.missing:
            lines.append(_("Palabras clave de la oferta que mi CV base no cita (úsalas solo si son ciertas en mi caso): "
                           "{names}").format(names=", ".join(ats.missing[:12])))
        if ats.failed:
            lines.append(_("Requisitos eliminatorios que no cumplo: {names}").format(names=", ".join(ats.failed)))
    return "\n".join(lines) + "\n"


_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_INLINE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")

_STYLE = """body{font-family:Arial,Helvetica,sans-serif;max-width:800px;margin:32px auto;padding:0 20px;color:#111;
line-height:1.45;font-size:11pt}h1{font-size:20pt;margin:0 0 4px}h2{font-size:13pt;border-bottom:1px solid #999;
margin:18px 0 6px;padding-bottom:2px;text-transform:uppercase}h3{font-size:11.5pt;margin:12px 0 2px}ul{margin:4px 0 8px;
padding-left:20px}p{margin:4px 0}@media print{body{margin:0;max-width:none}}"""


def _inline(text: str) -> str:
    escaped = html.escape(text)
    return _INLINE_ITALIC.sub(r"<em>\1</em>", _INLINE_BOLD.sub(r"<strong>\1</strong>", escaped))


def markdown_to_html(markdown: str, title: str = "") -> str:
    """Un Markdown sencillo (títulos, listas, negrita y cursiva) como HTML autocontenido y listo para imprimir o
    guardar como PDF desde el navegador. Todo el texto se escapa."""
    body: list[str] = []
    in_list = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        bullet = re.match(r"\s*[-*•]\s+(.*)", line)
        if bullet and not line.startswith("**"):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_inline(bullet.group(1))}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        heading = re.match(r"(#{1,3})\s+(.*)", line)
        if heading:
            level = len(heading.group(1))
            body.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif line.strip():
            body.append(f"<p>{_inline(line)}</p>")
    if in_list:
        body.append("</ul>")
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{_STYLE}</style></head><body>{''.join(body)}</body></html>")
