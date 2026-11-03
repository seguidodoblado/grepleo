"""Utilidades de interfaz compartidas: modo claro u oscuro en uso, iconos del sistema y diálogos pequeños."""
from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from ..i18n import _
from .theming import icon_choice


class Appearance:
    """Modo en uso (oscuro o claro) y tema GTK que tenía el sistema al arrancar."""
    dark = False
    system = ""


APPEARANCE = Appearance()

CSS = b"""
.fit-high { background: rgba(46, 160, 67, 0.35); border-radius: 9px; padding: 1px 8px; }
.fit-medium { background: rgba(210, 153, 34, 0.35); border-radius: 9px; padding: 1px 8px; }
.fit-low { background: rgba(218, 54, 51, 0.35); border-radius: 9px; padding: 1px 8px; }
.fit-unknown { background: rgba(128, 128, 128, 0.25); border-radius: 9px; padding: 1px 8px; }
"""


def install_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def pick_icon(*names: str) -> str:
    """El primer icono de la lista que exista en el tema del usuario ('' si ninguno): simbólico en el modo oscuro
    y de color en el claro (ver theming.icon_choice)."""
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    return icon_choice(names, APPEARANCE.dark, theme.has_icon)


def icon_button(icons: tuple[str, ...], text: str, **properties) -> Gtk.Button:
    """Botón con un icono del tema y su texto."""
    content = Gtk.Box(spacing=6)
    content.append(Gtk.Image(icon_name=pick_icon(*icons)))
    content.append(Gtk.Label(label=text))
    return Gtk.Button(child=content, **properties)


def labeled(text: str, widget: Gtk.Widget, vertical: bool = True) -> Gtk.Box:
    """Un campo con su etiqueta encima (o a la izquierda)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=4)
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("dim-label")
    box.append(label)
    box.append(widget)
    return box


def message(parent: Gtk.Window, text: str, detail: str = "") -> None:
    """Un aviso con un único botón."""
    Gtk.AlertDialog(message=text, detail=detail, buttons=[_("Aceptar")]).choose(parent, None, None)


def confirm(parent: Gtk.Window, text: str, detail: str, accept: str, callback: Callable[[], None]) -> None:
    """Pide confirmación; llama a `callback` solo si el usuario acepta."""
    dialog = Gtk.AlertDialog(message=text, detail=detail, buttons=[_("Cancelar"), accept],
                             cancel_button=0, default_button=1)

    def answered(source, result):
        try:
            choice = source.choose_finish(result)
        except Exception:  # noqa: BLE001 - cerrar el diálogo sin elegir es lo mismo que cancelar
            return
        if choice == 1:
            callback()

    dialog.choose(parent, None, answered)


def ask_text(parent: Gtk.Window, title: str, label: str, default: str, callback: Callable[[str], None]) -> None:
    """Una ventanita para pedir un texto corto; llama a `callback` con el texto si no se cancela."""
    window = Gtk.Window(title=title, transient_for=parent, modal=True, resizable=False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=16, margin_bottom=16,
                  margin_start=16, margin_end=16)
    entry = Gtk.Entry(text=default, activates_default=True, width_chars=36)
    box.append(labeled(label, entry))
    buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
    cancel = Gtk.Button(label=_("Cancelar"))
    accept = Gtk.Button(label=_("Aceptar"))
    accept.add_css_class("suggested-action")
    buttons.append(cancel)
    buttons.append(accept)
    box.append(buttons)
    window.set_child(box)
    window.set_default_widget(accept)

    def done(_button):
        text = entry.get_text().strip()
        if text:
            window.close()
            callback(text)

    cancel.connect("clicked", lambda _button: window.close())
    accept.connect("clicked", done)
    window.present()
