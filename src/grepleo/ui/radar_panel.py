"""La pestaña «Radar» de una oferta: la compatibilidad ATS estimada y, por tema, un radar con su leyenda lateral."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..ats import AtsEstimate
from ..i18n import _
from ..models import Fit
from ..radar import RadarData, known_axes, total_overlap
from .radar_legend import build_ats, build_legend
from .radar_view import RadarView


def percent(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)} %"


class RadarPanel(Gtk.ScrolledWindow):
    """Los radares de la oferta elegida, uno bajo otro, con scroll. Cada uno lleva su leyenda al lado si hay sitio
    (y debajo si el panel es estrecho)."""

    def __init__(self, **properties) -> None:
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, **properties)
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=6, margin_bottom=10,
                            margin_start=4, margin_end=8)
        self.set_child(self._box)
        self.summary = Gtk.Label(xalign=0, wrap=True)
        self.summary.add_css_class("title-4")
        self.views: list[RadarView] = []
        self.legends: list[Gtk.Box] = []
        self.ats_box: Gtk.Box | None = None
        self.set_data([], Fit.UNKNOWN)

    def set_data(self, radars: list[RadarData], fit: Fit, ats: AtsEstimate | None = None) -> None:
        while (child := self._box.get_first_child()) is not None:
            self._box.remove(child)
        self.views, self.legends, self.ats_box = [], [], None
        if not radars:
            self._box.append(Gtk.Label(label=_("Elige una oferta para ver sus radares."), xalign=0))
            return
        if ats is not None:
            self.ats_box = build_ats(ats)
            self._box.append(self.ats_box)
            self._box.append(Gtk.Separator())
        overall = total_overlap(radars)
        known, total = known_axes(radars)
        self.summary.set_text(
            _("Solape global: {percent}").format(percent=percent(overall)) + " · "
            + _("con datos en {known} de {total} ejes").format(known=known, total=total) if overall is not None
            else _("La oferta no pide nada que se pueda medir en tus radares."))
        self.summary.set_tooltip_text(_("Cuánto de lo que pide la oferta cubres con tus niveles: más solape, más "
                                        "posibilidades de encaje."))
        self._box.append(self.summary)
        for radar in radars:
            head = Gtk.Label(xalign=0)
            overlap = radar.overlap
            head.set_markup("<b>{title}</b> · {text}".format(
                title=GLib.markup_escape_text(radar.title),
                text=GLib.markup_escape_text(
                    _("solape {percent}").format(percent=percent(overlap)) if overlap is not None
                    else _("la oferta no pide nada de esto"))))
            self._box.append(head)
            view = RadarView(width_request=320)
            view.set_content_height(340)
            view.set_data(radar.labels, radar.levels, radar.demand, fit)
            legend = build_legend(radar, fit)
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2, min_children_per_line=1,
                               homogeneous=False, column_spacing=12, row_spacing=6)
            flow.append(view)
            flow.append(legend)
            self.views.append(view)
            self.legends.append(legend)
            self._box.append(flow)
