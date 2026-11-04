"""El editor de los radares por temas de un perfil: cada radar con su nombre, sus elementos y una vista previa."""
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..i18n import _
from ..models import Fit
from ..profiles import MAX_AXES, MIN_AXES, Profile, SkillRadar, format_axes, parse_axes
from ..radar import suggest_radars
from .common import pick_icon
from .radar_view import RadarView


class _Row(Gtk.Box):
    """Un radar: su nombre, la caja con sus elementos («AWS|amazon = 8», uno por línea) y su vista previa."""

    def __init__(self, radar: SkillRadar, on_remove: Callable[["_Row"], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6,
                         margin_start=8, margin_end=8)
        self.add_css_class("card")
        head = Gtk.Box(spacing=8)
        self.name = Gtk.Entry(text=radar.name, hexpand=True, placeholder_text=_("Nombre del radar (Cloud, Lenguajes…)"))
        head.append(self.name)
        remove = Gtk.Button(icon_name=pick_icon("user-trash", "edit-delete"), tooltip_text=_("Quitar este radar"))
        remove.connect("clicked", lambda _button: on_remove(self))
        head.append(remove)
        self.append(head)
        body = Gtk.Box(spacing=12, homogeneous=True)
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=6, bottom_margin=6, left_margin=6,
                                 right_margin=6)
        self.text.get_buffer().set_text(format_axes(radar.axes))
        self.text.get_buffer().connect("changed", self._changed)
        scroll = Gtk.ScrolledWindow(min_content_height=170, has_frame=True)
        scroll.set_child(self.text)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hint = Gtk.Label(xalign=0, wrap=True, label=_(
            "Un elemento por línea, con sinónimos y tu nivel de 0 a 10: AWS|amazon web services = 8"))
        hint.add_css_class("dim-label")
        left.append(hint)
        left.append(scroll)
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("error")
        left.append(self.status)
        body.append(left)
        self.preview = RadarView()
        self.preview.set_content_height(230)
        body.append(self.preview)
        self.append(body)
        self._changed()

    def text_value(self) -> str:
        buffer = self.text.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def radar(self) -> SkillRadar:
        return SkillRadar(self.name.get_text().strip(), parse_axes(self.text_value())[:MAX_AXES])

    def _changed(self, *_args) -> None:
        axes = parse_axes(self.text_value())
        if len(axes) < MIN_AXES or len(axes) > MAX_AXES:
            self.status.set_text(_("Un radar necesita entre {low} y {high} elementos (ahora hay {count}).").format(
                low=MIN_AXES, high=MAX_AXES, count=len(axes)))
        else:
            self.status.set_text("")
        axes = axes[:MAX_AXES]
        self.preview.set_data([axis.name for axis in axes], [float(axis.level) for axis in axes], None, Fit.UNKNOWN)


class RadarEditor(Gtk.Box):
    """Varios radares por temas. `get_profile` da el perfil tal como está ahora en el formulario, para proponer."""

    def __init__(self, radars: list[SkillRadar], get_profile: Callable[[], Profile]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._get_profile = get_profile
        self._rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.append(self._rows_box)
        self.rows: list[_Row] = []
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.START)
        add = Gtk.Button(label=_("Añadir radar"))
        add.connect("clicked", lambda _button: self.add(SkillRadar("")))
        propose = Gtk.Button(label=_("Proponer radares desde mis habilidades"),
                             tooltip_text=_("Agrupa por temas los requisitos de tu perfil; luego los puedes editar"))
        propose.connect("clicked", self._propose)
        buttons.append(add)
        buttons.append(propose)
        self.append(buttons)
        self.message = Gtk.Label(xalign=0, wrap=True)
        self.message.add_css_class("dim-label")
        self.append(self.message)
        for radar in radars:
            self.add(radar)

    def add(self, radar: SkillRadar) -> None:
        row = _Row(radar, self._remove)
        self.rows.append(row)
        self._rows_box.append(row)

    def _remove(self, row: _Row) -> None:
        self.rows.remove(row)
        self._rows_box.remove(row)

    def _propose(self, _button) -> None:
        proposed = suggest_radars(self._get_profile())
        existing = {row.name.get_text().strip().casefold() for row in self.rows}
        added = [radar for radar in proposed if radar.name.casefold() not in existing]
        for radar in added:
            self.add(radar)
        if added:
            self.message.set_text(_("Radares propuestos: {names}. Revisa los elementos y los niveles.").format(
                names=", ".join(radar.name for radar in added)))
        else:
            self.message.set_text(_("No hay nada que proponer: añade requisitos a tu perfil (al menos tres de un mismo "
                                    "tema) o ya tienes radares con esos nombres."))

    def radars(self) -> list[SkillRadar]:
        """Los radares tal como están: un nombre vacío con elementos pasa a llamarse «Radar»; sin nombre ni elementos,
        la fila se descarta."""
        result = []
        for row in self.rows:
            radar = row.radar()
            if not radar.name and not radar.axes:
                continue
            result.append(SkillRadar(radar.name or _("Radar"), radar.axes))
        return result
