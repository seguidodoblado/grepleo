"""El panel de una oferta: título, datos, criterios y descripción con lo de tu perfil resaltado."""
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk, Pango

from ..ats import AtsEstimate
from ..detail import BULLET, GOOD, HEADING, highlight_spans, structure_description
from ..i18n import _
from ..models import CriterionResult, Evaluation, Fit, Job, Status
from ..profiles import Profile, parse_term

_GREEN, _RED, _ORANGE, _GREY = (0.18, 0.63, 0.26), (0.85, 0.21, 0.20), (0.90, 0.49, 0.13), (0.5, 0.5, 0.5)
_FIT_COLORS = {Fit.HIGH: _GREEN, Fit.MEDIUM: _ORANGE, Fit.LOW: _RED, Fit.UNKNOWN: _GREY}
_STATUS_COLORS = {Status.MET: _GREEN, Status.MISSING: _RED, Status.UNKNOWN: _GREY, Status.PARTIAL: _ORANGE}


def _rgba(color: tuple[float, float, float], alpha: float = 1.0) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue, rgba.alpha = (*color, alpha)
    return rgba


def _criteria_groups(criteria: list[CriterionResult]) -> list[tuple[list[CriterionResult], str]]:
    """Los criterios por grupos (técnicas, blandas, condiciones) con su título; sin títulos si solo hay un grupo."""
    titles = (("hard", _("Habilidades técnicas")), ("soft", _("Habilidades blandas")), ("conditions", _("Condiciones")))
    groups = [([item for item in criteria if item.group == key], title) for key, title in titles]
    groups = [(items, title) for items, title in groups if items]
    return groups if len(groups) > 1 else [(items, "") for items, _title in groups]


class DetailView(Gtk.TextView):
    """Texto de solo lectura (se puede seleccionar y copiar) con estilos de etiqueta."""

    def __init__(self) -> None:
        super().__init__(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                         left_margin=4, right_margin=8, top_margin=4, bottom_margin=12)
        buffer = self.get_buffer()
        buffer.create_tag("title", weight=Pango.Weight.BOLD, scale=1.3, pixels_below_lines=3)
        buffer.create_tag("muted", foreground_rgba=_rgba(_GREY))
        buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        buffer.create_tag("italic", style=Pango.Style.ITALIC)
        buffer.create_tag("heading", weight=Pango.Weight.BOLD, scale=1.12, pixels_above_lines=14,
                          pixels_below_lines=4)
        buffer.create_tag("bullet", left_margin=22, indent=-14, pixels_below_lines=3)
        buffer.create_tag("paragraph", pixels_below_lines=8)
        buffer.create_tag("criterion", left_margin=22, indent=-18, pixels_below_lines=3)
        buffer.create_tag("subheading", weight=Pango.Weight.BOLD, foreground_rgba=_rgba(_GREY), pixels_above_lines=6,
                          pixels_below_lines=2)
        buffer.create_tag("good", background_rgba=_rgba(_GREEN, 0.30))
        buffer.create_tag("bad", background_rgba=_rgba(_RED, 0.30))
        buffer.create_tag("missing-text", foreground_rgba=_rgba(_RED))
        buffer.create_tag("met-text", foreground_rgba=_rgba(_GREEN))
        buffer.create_tag("partial-text", foreground_rgba=_rgba(_ORANGE))
        buffer.create_tag("critical", background_rgba=_rgba(_RED, 0.22))
        for status, color in _STATUS_COLORS.items():
            buffer.create_tag(f"status-{status.value}", weight=Pango.Weight.BOLD, foreground_rgba=_rgba(color))
        for fit, color in _FIT_COLORS.items():
            buffer.create_tag(f"fit-{fit.value}", weight=Pango.Weight.BOLD, background_rgba=_rgba(color, 0.35))

    # --- escritura ---------------------------------------------------------------------------------
    def _add(self, text: str, *tags: str) -> int:
        """Añade texto al final con esas etiquetas y devuelve dónde empezó (en caracteres)."""
        buffer = self.get_buffer()
        start = buffer.get_char_count()
        buffer.insert(buffer.get_end_iter(), text, -1)
        for tag in tags:
            buffer.apply_tag_by_name(tag, buffer.get_iter_at_offset(start), buffer.get_end_iter())
        return start

    def _tag_range(self, tag: str, start: int, end: int) -> None:
        buffer = self.get_buffer()
        buffer.apply_tag_by_name(tag, buffer.get_iter_at_offset(start), buffer.get_iter_at_offset(end))

    def show_message(self, text: str) -> None:
        self.get_buffer().set_text("", -1)
        self._add(text, "italic")

    def show_job(self, job: Job, evaluation: Evaluation, profile: Profile, salary: str,
                 ats: AtsEstimate | None = None) -> None:
        self.get_buffer().set_text("", -1)
        self._add(job.title + "\n", "title")
        place = " · ".join(part for part in (job.company, job.location, job.work_mode.label) if part)
        if place:
            self._add(place + "\n", "bold")
        facts = [salary if salary != "—" else "", job.experience_text, job.contract, job.studies_text,
                 _("Publicada el {date}").format(date=job.posted) if job.posted else ""]
        line = " · ".join(fact for fact in facts if fact)
        if line:
            self._add(line + "\n", "muted")
        self._add("\n")
        self._add(" " + _("Encaje: {fit}").format(fit=evaluation.fit.label) + " ", f"fit-{evaluation.fit.value}")
        if ats is not None:   # el detalle está en la pestaña Radar
            self._add("   " + _("ATS ≈ {percent} %").format(percent=ats.percent), "bold")
        notes = []
        if evaluation.category:
            notes.append(f"{_('Tipo')}: {evaluation.category}")
        if not job.full_description:
            notes.append(_("Ficha resumida"))
        if job.closed:
            notes.append(_("Posiblemente cerrada"))
        if notes:
            self._add("   " + " · ".join(notes), "muted")
        self._add("\n")

        self._add(_("Criterios") + "\n", "heading")
        for group, title in _criteria_groups(evaluation.criteria):
            if title:
                self._add(title + "\n", "subheading")
            for criterion in group:
                self._write_criterion(criterion)

        if job.description:
            self._add(_("Descripción") + "\n", "heading")
            self._write_description(job.description, profile)

    def _write_criterion(self, criterion: CriterionResult) -> None:
        missing = criterion.status is Status.MISSING
        color = (["missing-text"] if missing else ["met-text"] if criterion.status is Status.MET
                 else ["partial-text"] if criterion.status is Status.PARTIAL else [])
        start = self._add(criterion.status.symbol, f"status-{criterion.status.value}", "criterion")
        self._add("  ")
        self._add(criterion.name, "bold", *color)
        if criterion.required and missing:   # un imprescindible que no se cumple: toda la línea en rojo
            self._add("  " + _("imprescindible"), "bold", "missing-text")
        self._add(f" — {criterion.detail}" if criterion.detail else "", *color)
        end = self._add("\n")
        if criterion.required and missing:
            self._tag_range("critical", start, end)

    def _write_description(self, text: str, profile: Profile) -> None:
        good = [spec for spec in (*profile.all_must, *profile.all_nice) if parse_term(spec)[1]]
        for block in structure_description(text):
            if block.kind == HEADING:
                self._add(block.text + "\n", "heading")
                continue
            prefix = "•  " if block.kind == BULLET else ""
            start = self._add(prefix + block.text + "\n", "bullet" if block.kind == BULLET else "paragraph")
            for first, last, kind in highlight_spans(block.text, good, list(profile.avoid)):
                self._tag_range("good" if kind == GOOD else "bad", start + len(prefix) + first,
                                start + len(prefix) + last)
