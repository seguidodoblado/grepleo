"""El botón «Estudiar»: certificaciones oficiales y búsquedas de cursos para una habilidad que falta."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..i18n import _
from ..study import LAST_REVIEW, certifications_for, course_links


def study_button(name: str) -> Gtk.MenuButton:
    """Un botón que abre una ventanita con las certificaciones oficiales del tema (con enlace al organismo que las otorga)
    y búsquedas del tema en Udemy y Coursera, en español y en inglés. Los enlaces se abren en el navegador al pulsarlos."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8, margin_bottom=8, margin_start=10,
                  margin_end=10)

    def heading(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text, xalign=0, margin_top=4)
        label.add_css_class("heading")
        return label

    certs = certifications_for(name)
    if certs:
        box.append(heading(_("Certificaciones oficiales")))
        for cert in certs:
            link = Gtk.LinkButton.new_with_label(cert.url, f"{cert.name} · {cert.issuer}")
            link.set_halign(Gtk.Align.START)
            box.append(link)
    box.append(heading(_("Buscar cursos de {name}").format(name=name)))
    links = Gtk.Box(spacing=4)
    for label, url in course_links(name).items():
        link = Gtk.LinkButton.new_with_label(url, label)
        links.append(link)
    box.append(links)
    note = Gtk.Label(xalign=0, wrap=True, max_width_chars=52, margin_top=6, label=_(
        "Se abren en tu navegador; no se recomiendan cursos concretos. Las certificaciones se revisaron en {date}: "
        "comprueba en el enlace oficial que siguen vigentes.").format(date=LAST_REVIEW))
    note.add_css_class("dim-label")
    box.append(note)
    popover = Gtk.Popover()
    popover.set_child(box)
    return Gtk.MenuButton(label=_("Estudiar"), popover=popover, valign=Gtk.Align.CENTER, css_classes=["flat"],
                          tooltip_text=_("Certificaciones oficiales y búsqueda de cursos en Udemy y Coursera"))
