"""El minimapa de los radares: una miniatura por radar para ver de un vistazo dónde encaja la oferta."""
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from ..i18n import _
from ..models import Fit
from ..radar import RadarData
from .radar_view import RadarView

HIGH, MEDIUM = 0.75, 0.45      # los mismos umbrales que el encaje
THUMB = (112, 100)             # tamaño de cada miniatura
THUMB_FIRST = (150, 134)       # el radar general, el primero, algo más grande


def percent(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)} %"


def overlap_class(overlap: float | None) -> str:
    """El color de una miniatura según cuánto cubres de lo que pide la oferta en ese radar."""
    if overlap is None:
        return "none"
    return "high" if overlap >= HIGH else "medium" if overlap >= MEDIUM else "low"


class RadarMinimap(Gtk.FlowBox):
    """Una tira de miniaturas con el nombre y el solape de cada radar; al pulsar una se va a su radar completo."""

    def __init__(self, radars: list[RadarData], fit: Fit, on_pick: Callable[[int], None]) -> None:
        super().__init__(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False, min_children_per_line=2,
                         max_children_per_line=8, column_spacing=6, row_spacing=6, halign=Gtk.Align.START)
        self.thumbs: list[Gtk.Box] = []
        for index, radar in enumerate(radars):
            thumb = self._thumb(index, radar, fit, on_pick)
            self.thumbs.append(thumb)
            self.append(thumb)

    @staticmethod
    def _thumb(index: int, radar: RadarData, fit: Fit, on_pick: Callable[[int], None]) -> Gtk.Box:
        overlap = radar.overlap
        width, height = THUMB_FIRST if index == 0 else THUMB
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, width_request=width)
        card.add_css_class("radar-thumb")
        card.add_css_class(f"radar-thumb-{overlap_class(overlap)}")
        view = RadarView(compact=True, width_request=width, content_height=height)
        view.set_content_width(width)
        view.set_data(radar.labels, radar.levels, radar.demand, fit)
        card.append(view)
        title = Gtk.Label(label=radar.title, ellipsize=Pango.EllipsizeMode.END, max_width_chars=14)
        title.add_css_class("heading")
        card.append(title)
        text = Gtk.Label(label=percent(overlap))
        text.add_css_class("dim-label")
        card.append(text)
        card.set_tooltip_text(
            radar.title + "\n" + (_("solape {percent}").format(percent=percent(overlap)) if overlap is not None
                                  else _("la oferta no pide nada de esto")))
        click = Gtk.GestureClick()
        click.connect("released", lambda *_args, i=index: GLib.idle_add(on_pick, i))
        card.add_controller(click)
        return card
