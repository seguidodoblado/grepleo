"""Utilidades de interfaz compartidas: modo claro u oscuro en uso, iconos del sistema y diálogos pequeños."""
from collections.abc import Callable
from pathlib import Path

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
.row-fit-high { background: rgba(46, 160, 67, 0.30); }
.row-fit-medium { background: rgba(230, 126, 34, 0.32); }
.row-fit-low { background: rgba(218, 54, 51, 0.30); }
.row-fit-unknown { background: rgba(128, 128, 128, 0.18); }
.wide-scroll scrollbar.vertical { min-width: 18px; }
.wide-scroll scrollbar.vertical slider { min-width: 12px; min-height: 56px; border-radius: 6px; }
.level-row { padding: 4px 8px; border-radius: 6px; }
.level-active { background: rgba(53, 132, 228, 0.28); }
.radar-card { border-radius: 10px; padding: 10px 14px; background: rgba(128, 128, 128, 0.07);
              border-left: 5px solid rgba(128, 128, 128, 0.5); }
.radar-card-high { border-left-color: rgba(46, 160, 67, 0.95);
                   background-image: linear-gradient(90deg, rgba(46, 160, 67, 0.16), rgba(46, 160, 67, 0.02)); }
.radar-card-medium { border-left-color: rgba(230, 126, 34, 0.95);
                     background-image: linear-gradient(90deg, rgba(230, 126, 34, 0.18), rgba(230, 126, 34, 0.02)); }
.radar-card-low { border-left-color: rgba(218, 54, 51, 0.95);
                  background-image: linear-gradient(90deg, rgba(218, 54, 51, 0.16), rgba(218, 54, 51, 0.02)); }
.radar-badge { font-weight: bold; opacity: 0.85; }
.radar-thumb { border-radius: 8px; padding: 4px 6px; }
.radar-thumb-high { background: rgba(46, 160, 67, 0.22); }
.radar-thumb-medium { background: rgba(230, 126, 34, 0.24); }
.radar-thumb-low { background: rgba(218, 54, 51, 0.22); }
.radar-thumb-none { background: rgba(128, 128, 128, 0.12); opacity: 0.6; }
.map-pin { min-width: 22px; min-height: 22px; border-radius: 12px; border: 2px solid rgba(255, 255, 255, 0.95);
           color: white; font-weight: bold; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.55); }
.map-dark { filter: invert(1) hue-rotate(180deg); }
.map-pin-undo { filter: invert(1) hue-rotate(180deg); }
.map-pin-hybrid { border-radius: 6px; }
.map-pin.map-pin-remote { background: white; border-width: 4px; }
.map-pin.map-pin-remote.map-pin-high { color: rgb(46, 160, 67); border-color: rgb(46, 160, 67); }
.map-pin.map-pin-remote.map-pin-medium { color: rgb(230, 126, 34); border-color: rgb(230, 126, 34); }
.map-pin.map-pin-remote.map-pin-low { color: rgb(218, 54, 51); border-color: rgb(218, 54, 51); }
.map-pin.map-pin-remote.map-pin-unknown { color: rgb(128, 128, 128); border-color: rgb(128, 128, 128); }
.map-legend { background: rgba(255, 255, 255, 0.88); color: #222; border-radius: 8px; padding: 6px 10px; font-size: 90%; }
.map-legend-dark { background: rgba(32, 32, 32, 0.88); color: #eee; }
.map-legend-swatch { min-width: 14px; min-height: 14px; border-width: 2px; box-shadow: none; }
.map-pin-high { background: rgb(46, 160, 67); }
.map-pin-medium { background: rgb(230, 126, 34); }
.map-pin-low { background: rgb(218, 54, 51); }
.map-pin-unknown { background: rgb(128, 128, 128); }
.skill-card { border-radius: 10px; padding: 12px 16px; }
.skill-card-gap { background-image: linear-gradient(135deg, rgba(218, 54, 51, 0.42), rgba(218, 54, 51, 0.08));
                  border-left: 5px solid rgba(218, 54, 51, 0.95); }
.skill-card-strength { background-image: linear-gradient(135deg, rgba(46, 160, 67, 0.40), rgba(46, 160, 67, 0.08));
                       border-left: 5px solid rgba(46, 160, 67, 0.95); }
.skill-card-info { background-image: linear-gradient(135deg, rgba(53, 132, 228, 0.36), rgba(53, 132, 228, 0.07));
                   border-left: 5px solid rgba(53, 132, 228, 0.95); }
.skill-card-info progressbar progress { background: rgba(53, 132, 228, 0.95); }
.skill-card progressbar.bar-fit-high progress { background: rgba(46, 160, 67, 0.95); }
.skill-card progressbar.bar-fit-medium progress { background: rgba(230, 126, 34, 0.95); }
.skill-card progressbar.bar-fit-low progress { background: rgba(218, 54, 51, 0.95); }
.skill-card-gap progressbar progress { background: rgba(218, 54, 51, 0.95); }
.skill-card-strength progressbar progress { background: rgba(46, 160, 67, 0.95); }
"""


ICONS_DIR = Path(__file__).parent / "icons"   # los iconos de las fuentes: monogramas propios, no los logotipos


def source_icon(source_id: str) -> str:
    """El nombre del icono de una fuente de ofertas ('' si no hay)."""
    name = f"grepleo-source-{source_id}"
    return name if (ICONS_DIR / f"{name}.svg").exists() else ""


def wide_scrollbars(scroll: Gtk.ScrolledWindow) -> Gtk.ScrolledWindow:
    """Una barra de desplazamiento ancha y siempre visible (la fina que aparece al pasar el ratón cuesta de coger)."""
    scroll.set_overlay_scrolling(False)
    scroll.add_css_class("wide-scroll")
    return scroll


def install_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    Gtk.IconTheme.get_for_display(display).add_search_path(str(ICONS_DIR))


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


def link_icon(platform_id: str) -> str:
    """El nombre del icono de una plataforma de perfiles profesionales ('' si no hay)."""
    name = f"grepleo-link-{platform_id}"
    return name if (ICONS_DIR / f"{name}.svg").exists() else ""


def vte_available() -> bool:
    """El terminal embebible para GTK 4 (gir1.2-vte-3.91), comprobado sin cargarlo."""
    return "3.91" in gi.Repository.get_default().enumerate_versions("Vte")


def block_parent(window: Gtk.Window, parent: Gtk.Window | None) -> None:
    """Hace que `window` sea una ventana independiente que bloquea a `parent` mientras esté abierta.

    No se le pone `transient_for` ni `modal`: con ventana madre, GTK la declara «diálogo» y Muffin (Cinnamon) y otros
    gestores no dejan maximizarla. Así se comporta como una ventana normal (maximizable) y la principal queda sin
    responder hasta que se cierra."""
    if parent is None:
        return

    def block(*_args) -> None:   # al mostrarse, no al crearse: una ventana que no llega a mostrarse no deja a la principal bloqueada
        parent.set_sensitive(False)

    window.connect("map", block)

    def restore(*_args) -> bool:
        parent.set_sensitive(True)
        return False

    window.connect("close-request", restore)
    window.connect("unrealize", restore)   # GTK 4 ya no emite «destroy»; esto cubre también un destroy() directo


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
