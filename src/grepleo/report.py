"""Informe exportable (HTML autocontenido y CSV) con lo que muestra la aplicación, sin GTK ni red."""
from __future__ import annotations

import csv
import html
from datetime import datetime, timezone
from pathlib import Path

from .i18n import _, ngettext
from .models import Evaluation, Fit, Job, Status
from .panorama import Panorama
from .profiles import Profile

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: str) -> str:
    """Un texto de una oferta no debe ejecutarse como fórmula al abrir el CSV en una hoja de cálculo."""
    return "'" + value if value.startswith(_FORMULA_START) else value


def export_csv(path: Path, jobs: list[Job], evaluations: dict[str, Evaluation], source_names: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([_("Empresa"), _("Puesto"), _("Tipo"), _("Ubicación"), _("Modalidad"), _("Salario"),
                         _("Experiencia"), _("Encaje"), _("Criterios"), _("Fuente"), _("Publicada"), _("Enlace")])
        for job in jobs:
            result = evaluations.get(job.key)
            writer.writerow([_safe_cell(value) for value in (
                job.company, job.title, result.category if result else "", job.location, job.work_mode.label,
                job.salary_text, job.experience_text, result.fit.label if result else "",
                result.summary if result else "", source_names.get(job.source, job.source), job.posted, job.url)])


_CSS = """
body{font:15px/1.5 system-ui,sans-serif;margin:0;background:#f5f6f8;color:#1c2330}
main{max-width:1200px;margin:0 auto;padding:24px 16px}
h1{font-size:28px;margin:0 0 6px} h2{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#59627a}
.card{background:#fff;border:1px solid #dfe3ea;border-radius:10px;padding:16px 20px;margin:16px 0}
.bars{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:6px 28px}
.bar{display:flex;align-items:center;gap:8px}.bar span:first-child{width:110px}
.bar i{flex:1;height:8px;background:#e6e9ef;border-radius:4px;position:relative;overflow:hidden}
.bar i b{position:absolute;left:0;top:0;bottom:0;background:#2f5d8a}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
input,select{font:inherit;padding:6px 10px;border:1px solid #ccd2dc;border-radius:8px;background:#fff}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dfe3ea;border-radius:10px}
th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#59627a;text-align:left;padding:10px 12px}
td{padding:10px 12px;border-top:1px solid #eceff4;vertical-align:top}
.fit{display:inline-block;padding:1px 10px;border-radius:99px;font-size:12px;font-weight:600}
.fit-high{background:#d8f1e1;color:#1c6b3a}.fit-medium{background:#fdf0c9;color:#7a5a00}
.fit-low{background:#fbdcdc;color:#8a2323}.fit-unknown{background:#e6e9ef;color:#59627a}
.tag{display:inline-block;margin:2px 3px 0 0;padding:0 7px;border-radius:5px;font:12px monospace}
.met{background:#d8f1e1}.partial{background:#fdecc8}.missing{background:#fbdcdc}.unknown{background:#e6e9ef}
.muted{color:#59627a;font-size:13px}
"""

_SCRIPT = """
const rows=[...document.querySelectorAll('tbody tr')];
const q=document.getElementById('q'),f=document.getElementById('fit'),c=document.getElementById('count');
function apply(){const t=q.value.toLowerCase();let n=0;
rows.forEach(r=>{const ok=r.textContent.toLowerCase().includes(t)&&(!f.value||r.dataset.fit===f.value);
r.style.display=ok?'':'none';if(ok)n++;});c.textContent=n+' / '+rows.length;}
q.addEventListener('input',apply);f.addEventListener('change',apply);apply();
"""


def _tags(result: Evaluation | None) -> str:
    if not result:
        return ""
    return "".join(f'<span class="tag {item.status.value}" title="{html.escape(item.detail)}">'
                   f"{item.status.symbol} {html.escape(item.name)}</span>" for item in result.criteria)


def export_html(path: Path, profile: Profile | None, jobs: list[Job], evaluations: dict[str, Evaluation],
                panorama: Panorama, source_names: dict[str, str], title: str, language: str = "es") -> None:
    esc = html.escape
    today = datetime.now(timezone.utc).astimezone().date().isoformat()
    maximum = max((item.count for item in panorama.requirements), default=0) or 1
    bars = "".join(
        f'<div class="bar"><span>{esc(item.name)}</span><i><b style="width:{100 * item.count // maximum}%"></b></i>'
        f"<span>{item.count}</span></div>" for item in panorama.requirements[:20] if item.count)
    insights = "".join(f"<li>{esc(text)}</li>" for text in panorama.insights)
    options = "".join(f'<option value="{fit.value}">{esc(fit.label)}</option>' for fit in Fit)
    rows = []
    for job in jobs:
        result = evaluations.get(job.key)
        fit = result.fit if result else Fit.UNKNOWN
        link = (f'<a href="{esc(job.url, quote=True)}" rel="noopener noreferrer">'
                f"{esc(source_names.get(job.source, job.source))}</a>") if job.url.startswith(("http://", "https://")) \
            else esc(source_names.get(job.source, job.source))
        notes = []
        if job.posted:
            notes.append(_("Publicada el {date}").format(date=job.posted))
        if not job.full_description:
            notes.append(_("Ficha resumida"))
        if job.closed:
            notes.append(_("Posiblemente cerrada"))
        if job.salary_estimated:
            notes.append(_("Salario estimado"))
        rows.append(
            f'<tr data-fit="{fit.value}"><td><b>{esc(job.company)}</b><div class="muted">{esc(job.title)}</div></td>'
            f"<td>{esc(result.category if result else '')}</td><td>{esc(job.location)}<div class=\"muted\">"
            f"{esc(job.work_mode.label)}</div></td><td>{esc(job.salary_text) or '—'}</td>"
            f"<td>{esc(job.experience_text) or '—'}</td><td>{_tags(result)}"
            f'<div class="muted">{esc(" · ".join(notes))}</div></td>'
            f'<td><span class="fit fit-{fit.value}">{esc(fit.label)}</span>'
            f'<div class="muted">{esc(result.summary if result else "")}</div></td><td>{link}</td></tr>')
    by_source = ", ".join(f"{count} {esc(source_names.get(source, source))}" for source, count in sorted(
        {s: sum(1 for job in jobs if job.source == s) for s in {job.source for job in jobs}}.items()))
    context = (_("Evaluado con el perfil «{name}»: {headline}").format(name=profile.name, headline=profile.headline)
               if profile else "")
    footer = ngettext("Muestra de {count} oferta ({sources}). ", "Muestra de {count} ofertas ({sources}). ",
                      len(jobs)).format(count=len(jobs), sources=by_source)
    footer += _("Las fichas resumidas no traen la descripción completa y algunas ofertas pueden estar cerradas. "
                "Los salarios marcados como estimados los calcula el portal, no la empresa.")
    document = f"""<!doctype html>
<html lang="{esc(language)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>{_CSS}</style></head><body><main>
<h1>{esc(title)}</h1><p class="muted">{esc(_("Generado el {date} con Grepleo.").format(date=today))} {esc(context)}</p>
<div class="card"><h2>{esc(_("Qué piden: ofertas con detalle que mencionan cada requisito"))}</h2>
<div class="bars">{bars}</div></div>
<div class="card"><h2>{esc(_("Lo que se ve en esta muestra"))}</h2><ul>{insights}</ul></div>
<div class="controls"><input id="q" type="search" placeholder="{esc(_("Buscar empresa, puesto o requisito"))}">
<select id="fit"><option value="">{esc(_("Encaje: todos"))}</option>{options}</select>
<span id="count" class="muted"></span></div>
<table><thead><tr><th>{esc(_("Empresa · Puesto"))}</th><th>{esc(_("Tipo"))}</th><th>{esc(_("Ubicación"))}</th>
<th>{esc(_("Salario"))}</th><th>{esc(_("Experiencia"))}</th><th>{esc(_("Criterios"))}</th>
<th>{esc(_("Encaje"))}</th><th>{esc(_("Enlace"))}</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<p class="muted">{esc(footer)}</p></main><script>{_SCRIPT}</script></body></html>
"""
    path.write_text(document, encoding="utf-8")


def status_counts(result: Evaluation) -> dict[Status, int]:
    return {status: result.count(status) for status in Status}
