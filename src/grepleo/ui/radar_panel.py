"""La pestaña «Radar» de una oferta: la compatibilidad ATS estimada y, por tema, un radar con su leyenda lateral."""
import gi

gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Graphene, Gtk, Pango

from ..ats import AtsEstimate
from ..i18n import _
from ..models import Fit
from ..radar import RadarData, known_axes, total_overlap
from .common import wide_scrollbars
from .radar_legend import build_ats, build_legend
from .radar_minimap import RadarMinimap, overlap_class, percent
from .radar_view import RadarView


class RadarPanel(Gtk.ScrolledWindow):
    """Los radares de la oferta elegida, uno bajo otro, con scroll. Cada uno lleva su leyenda al lado si hay sitio
    (y debajo si el panel es estrecho)."""

    def __init__(self, **properties) -> None:
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, **properties)
        wide_scrollbars(self)
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=6, margin_bottom=10,
                            margin_start=4, margin_end=8)
        self.set_child(self._box)
        self.summary = Gtk.Label(xalign=0, wrap=True)
        self.summary.add_css_class("title-4")
        self.views: list[RadarView] = []
        self.legends: list[Gtk.Box] = []
        self.cards: list[Gtk.Box] = []
        self.minimap: RadarMinimap | None = None
        self.ats_box: Gtk.Box | None = None
        self.set_data([], Fit.UNKNOWN)

    def set_data(self, radars: list[RadarData], fit: Fit, ats: AtsEstimate | None = None) -> None:
        while (child := self._box.get_first_child()) is not None:
            self._box.remove(child)
        self.views, self.legends, self.cards, self.minimap, self.ats_box = [], [], [], None, None
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
        if len(radars) >= 2:   # con un solo radar no hay nada que resumir
            self.minimap = RadarMinimap(radars, fit, self.scroll_to_radar)
            self._box.append(self.minimap)
        for radar in radars:
            overlap = radar.overlap
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=4)
            card.add_css_class("radar-card")
            card.add_css_class(f"radar-card-{overlap_class(overlap)}")
            # el título y el solape en una fila que se parte en dos si el panel es estrecho
            head = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2, min_children_per_line=1,
                               homogeneous=False, column_spacing=12, row_spacing=2)
            title = Gtk.Label(label=radar.title, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
            title.add_css_class("title-4")
            badge = Gtk.Label(label=_("solape {percent}").format(percent=percent(overlap)) if overlap is not None
                              else _("la oferta no pide nada de esto"), xalign=0)
            badge.add_css_class("radar-badge")
            head.append(title)
            head.append(badge)
            card.append(head)
            view = RadarView(width_request=320)
            view.set_content_height(340)
            view.set_data(radar.labels, radar.levels, radar.demand, fit)
            legend = build_legend(radar, fit)
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2, min_children_per_line=1,
                               homogeneous=False, column_spacing=12, row_spacing=6)
            flow.append(view)
            flow.append(legend)
            card.append(flow)
            self.views.append(view)
            self.legends.append(legend)
            self.cards.append(card)
            self._box.append(card)

    def scroll_to_radar(self, index: int) -> bool:
        """Desplaza el panel hasta la tarjeta del radar `index` (al pulsar su miniatura)."""
        if 0 <= index < len(self.cards):
            point = self.cards[index].compute_point(self._box, Graphene.Point().init(0, 0))
            if point[0]:
                adjustment = self.get_vadjustment()
                adjustment.set_value(max(0.0, point[1].y - 6))
        return False
