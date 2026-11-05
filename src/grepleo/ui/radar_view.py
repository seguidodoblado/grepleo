"""El radar de competencias: tu polígono (más intenso hacia los extremos) y el de la oferta encima."""
import math

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..i18n import _
from ..models import Fit
from ..radar import SCALE, drawn_value, polygon_points

_BLUE = (0.20, 0.52, 0.89)
_FIT_COLORS = {Fit.HIGH: (0.18, 0.63, 0.26), Fit.MEDIUM: (0.90, 0.49, 0.13), Fit.LOW: (0.85, 0.21, 0.20),
               Fit.UNKNOWN: (0.5, 0.5, 0.5)}
RINGS = 5


def _short(label: str, limit: int = 16) -> str:
    return label if len(label) <= limit else label[:limit - 1] + "…"


class RadarView(Gtk.DrawingArea):
    """Un pentágono con anillos. Tu perfil se rellena con un degradado que se intensifica hacia los extremos; la
    oferta se dibuja encima como contorno con el color de su encaje."""

    def __init__(self, compact: bool = False, **properties) -> None:
        """`compact`: la miniatura del minimapa, sin etiquetas, leyenda ni sugerencia de ejes."""
        properties.setdefault("content_height", 230)
        super().__init__(hexpand=not compact, **properties)
        self._compact = compact
        self._labels: list[str] = []
        self._levels: list[float] = []
        self._demand: list[float | None] = []
        self._fit = Fit.UNKNOWN
        self.set_draw_func(self._draw)

    def set_data(self, labels: list[str], levels: list[float], demand: list[float | None] | None,
                 fit: Fit = Fit.UNKNOWN, notes: list[str] | None = None) -> None:
        """`labels`, `levels` (tu nivel) y `demand` (lo que pide la oferta; None en un eje = no se sabe) van por ejes."""
        self._labels, self._levels, self._demand, self._fit = labels, levels, demand or [], fit
        if self._compact:
            self.queue_draw()
            return
        lines = []
        for index, label in enumerate(labels):
            asked = self._demand[index] if index < len(self._demand) else None
            line = _("{axis}: tú {mine} · oferta {asked}").format(
                axis=label, mine=f"{levels[index]:.0f}", asked="?" if asked is None else f"{asked:.0f}")
            if notes and index < len(notes) and notes[index]:
                line += f" ({notes[index]})"   # qué hay detrás: «cita 10 o más tecnologías», «pide 3 años»…
            lines.append(line)
        self.set_tooltip_text("\n".join(lines) or None)
        self.queue_draw()

    # --- dibujo ------------------------------------------------------------------------------------
    def _draw(self, _area, cr, width, height) -> None:
        foreground = self.get_color()
        ink = (foreground.red, foreground.green, foreground.blue)
        count = max(len(self._labels), 3)
        if self._compact:
            center_x, center_y = width / 2, height / 2
            radius = max(8.0, min(width, height) / 2 - 6)
        else:
            center_x, center_y = width / 2, (height - 16) / 2
            # el radio aprovecha el alto (con sitio para las etiquetas de arriba y abajo y la leyenda) y el ancho
            # (con sitio para las etiquetas de los lados)
            radius = max(20.0, min(width / 2 - 80, (height - 36) / 2 - 22))

        # anillos y ejes
        cr.set_line_width(1)
        for ring in range(1, RINGS + 1):
            points = polygon_points([SCALE * ring / RINGS] * count, center_x, center_y, radius)
            self._path(cr, points)
            cr.set_source_rgba(*ink, 0.22 if ring < RINGS else 0.45)
            cr.stroke()
        for x, y in polygon_points([SCALE] * count, center_x, center_y, radius):
            cr.move_to(center_x, center_y)
            cr.line_to(x, y)
            cr.set_source_rgba(*ink, 0.22)
            cr.stroke()

        # tu perfil: más color cuanto más lejos del centro
        if self._levels:
            import cairo  # solo con la interfaz; la lógica del radar no lo necesita
            gradient = cairo.RadialGradient(center_x, center_y, 0, center_x, center_y, radius)
            gradient.add_color_stop_rgba(0.0, *_BLUE, 0.06)
            gradient.add_color_stop_rgba(1.0, *_BLUE, 0.85)
            self._path(cr, polygon_points([drawn_value(level) for level in self._levels], center_x, center_y, radius))
            cr.set_source(gradient)
            cr.fill_preserve()
            cr.set_source_rgba(*_BLUE, 0.95)
            cr.set_line_width(1.5)
            cr.stroke()

        # la oferta encima
        if self._demand:
            color = _FIT_COLORS[self._fit]
            asked = polygon_points([drawn_value(value) for value in self._demand], center_x, center_y, radius)
            self._path(cr, asked)
            cr.set_source_rgba(*color, 0.14)
            cr.fill_preserve()
            cr.set_source_rgba(*color, 1.0)
            cr.set_line_width(2.5)
            cr.set_dash([6, 3])
            cr.stroke()
            cr.set_dash([])
            for value, (x, y) in zip(self._demand, asked, strict=True):
                if self._compact:
                    break
                cr.arc(x, y, 3.2, 0, 2 * math.pi)
                cr.set_source_rgba(*color, 1.0)
                if value is None:   # un eje que no se puede saber: círculo hueco, con «?» en la etiqueta
                    cr.set_line_width(1.5)
                    cr.stroke()
                else:
                    cr.fill()

        if self._compact:
            return
        # etiquetas de los ejes
        cr.set_font_size(11)
        positions = polygon_points([SCALE * 1.32] * count, center_x, center_y, radius)
        for index, (label, (x, y)) in enumerate(zip(self._labels, positions, strict=False)):
            unknown = self._demand and index < len(self._demand) and self._demand[index] is None
            text = _short(label) + (" ?" if unknown else "")
            extents = cr.text_extents(text)
            cr.move_to(x - extents.width / 2 - extents.x_bearing, y + extents.height / 2)
            cr.set_source_rgba(*ink, 0.9)
            cr.show_text(text)

        # leyenda
        cr.set_font_size(10)
        legend_y = height - 6
        cr.set_source_rgba(*_BLUE, 0.9)
        cr.rectangle(8, legend_y - 8, 10, 8)
        cr.fill()
        cr.set_source_rgba(*ink, 0.8)
        cr.move_to(22, legend_y)
        cr.show_text(_("Tú"))
        if self._demand:
            color = _FIT_COLORS[self._fit]
            cr.set_source_rgba(*color, 1.0)
            cr.set_line_width(2.5)
            cr.set_dash([4, 2])
            cr.move_to(58, legend_y - 4)
            cr.line_to(74, legend_y - 4)
            cr.stroke()
            cr.set_dash([])
            cr.set_source_rgba(*ink, 0.8)
            cr.move_to(80, legend_y)
            cr.show_text(_("Lo que pide la oferta"))

    @staticmethod
    def _path(cr, points) -> None:
        cr.new_path()
        cr.move_to(*points[0])
        for point in points[1:]:
            cr.line_to(*point)
        cr.close_path()
