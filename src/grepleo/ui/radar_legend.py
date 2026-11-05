"""La leyenda lateral de un radar y el cuadro de la compatibilidad ATS estimada."""
from gi.repository import GLib, Gtk

from ..ats import POSSIBLE, AtsEstimate
from ..i18n import _, ngettext
from ..models import Fit
from ..radar import COVERED, MISSING, NOT_ASKED, RadarData, coverage_points, legend_rows, main_gaps

_GREEN, _RED, _GREY, _BLUE = "#2ea043", "#d9342b", "#8b949e", "#3385e0"
_FIT_HEX = {Fit.HIGH: "#2ea043", Fit.MEDIUM: "#e67e22", Fit.LOW: "#d9342b", Fit.UNKNOWN: "#8b949e"}
MAX_LISTED = 8


def _esc(text: str) -> str:
    return GLib.markup_escape_text(text)


def _label(markup: str, **properties) -> Gtk.Label:
    # sin selección: con ella, GTK marca el primer texto al enfocar la ventana; y con un ancho natural acotado la leyenda
    # cabe al lado del radar en vez de ocupar toda una línea
    label = Gtk.Label(xalign=0, wrap=True, max_width_chars=38, **properties)
    label.set_markup(markup)
    return label


def _number(value: float) -> str:
    return f"{value:.0f}"


def build_legend(radar: RadarData, fit: Fit, market: bool = False) -> Gtk.Box:
    """Lo que se ve en un radar, dicho con palabras: qué es cada polígono, cuánto cubres y qué pide la oferta de cada eje.

    Con `market`, lo que pide son las ofertas en conjunto (la media entre las que lo piden)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_start=4, margin_end=4,
                  width_request=250, valign=Gtk.Align.START)
    box.append(_label(f"<span foreground='{_BLUE}'>■</span> <b>{_esc(_('Tú'))}</b>: "
                      + _esc(_("tu nivel de 0 a 10 en cada eje"))))
    if market:
        box.append(_label(f"<span foreground='{_FIT_HEX[fit]}'>┅</span> <b>{_esc(_('Lo que piden las ofertas'))}</b>: "
                          + _esc(_("la media entre las ofertas que lo piden: 5 si solo lo mencionan, 7 si lo valoran y "
                                   "10 si es requisito. Donde tu zona azul llega más lejos que la línea, lo cubres."))))
    else:
        box.append(_label(f"<span foreground='{_FIT_HEX[fit]}'>┅</span> <b>{_esc(_('Lo que pide la oferta'))}</b>: "
                          + _esc(_("0 si no lo pide, 5 si solo lo menciona, 7 si lo valora y 10 si es requisito. "
                                   "Donde tu zona azul llega más lejos que la línea, lo cubres."))))
        box.append(_label(f"<span foreground='{_GREY}'>○</span> <b>?</b>: " + _esc(_("la oferta no permite saberlo"))))

    covered, asked = coverage_points(radar)
    overlap = radar.overlap
    if overlap is None:
        text = _("Ninguna oferta pide nada medible en este radar.") if market else _(
            "La oferta no pide nada medible en este radar.")
        box.append(_label("<b>" + _esc(text) + "</b>", margin_top=6))
    else:
        text = (_("cubres {covered} de {asked} puntos de lo que piden las ofertas, contando cada eje según cuántas lo piden")
                if market else _("cubres {covered} de {asked} puntos de lo que pide la oferta"))
        box.append(_label("<b>" + _esc(_("Solape {percent} %").format(percent=round(overlap * 100))) + "</b> · "
                          + _esc(text.format(covered=_number(covered), asked=_number(asked))), margin_top=6))
    box.append(Gtk.Separator(margin_top=2, margin_bottom=2))
    for row in legend_rows(radar):
        head = f"<b>{_esc(row.label)}</b>  " + _esc(_("tú {mine}").format(mine=_number(row.mine))) + " · " + _esc(
            _("pide {asked}").format(asked="?" if row.asked is None else _number(row.asked)))
        if row.status == COVERED:
            verdict = f"<span foreground='{_GREEN}'>✓ {_esc(_('lo cubres'))}</span>"
        elif row.status == MISSING:
            gap = _number(row.gap)
            text = ngettext("te falta {gap} punto", "te faltan {gap} puntos", round(row.gap)).format(gap=gap)
            verdict = f"<span foreground='{_RED}'>✗ {_esc(text)}</span>"
        elif row.status == NOT_ASKED:
            verdict = f"<span foreground='{_GREY}'>· {_esc(_('no lo pide'))}</span>"
        else:
            verdict = f"<span foreground='{_GREY}'>? {_esc(_('no se sabe'))}</span>"
        detail = f"<small>{_esc(row.note)} — {verdict}</small>" if row.note else f"<small>{verdict}</small>"
        box.append(_label(head + "\n" + detail))
    gaps = main_gaps(radar)
    if gaps:
        box.append(_label("<b>" + _esc(_("Lo que más te falta")) + "</b>: " + _esc(", ".join(
            f"{row.label} (−{_number(row.gap)})" for row in gaps)), margin_top=4))
    return box


def build_ats(estimate: AtsEstimate) -> Gtk.Box:
    """El cuadro de la compatibilidad ATS: el porcentaje, el veredicto y de dónde sale."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    title = Gtk.Label(xalign=0, wrap=True)
    title.set_markup("<big><b>" + _esc(_("Compatibilidad ATS estimada: {percent} %").format(percent=estimate.percent))
                     + "</b></big>")
    title.set_tooltip_text(_("Un ATS es el programa con el que muchas empresas filtran los CV antes de que los lea una "
                             "persona. Es una estimación local: cada empresa configura el suyo."))
    box.append(title)
    bar = Gtk.ProgressBar(fraction=estimate.percent / 100)
    box.append(bar)
    verdict_color = _GREEN if estimate.percent >= 70 else "#e67e22" if estimate.percent >= 45 else _RED
    box.append(_label(f"<span foreground='{verdict_color}'><b>{_esc(estimate.verdict)}</b></span> · "
                      + _esc(_("fiabilidad {level}").format(level=estimate.reliability_label))))
    total = len(estimate.found) + len(estimate.missing)
    lines = []
    if estimate.keyword_score is not None:
        lines.append(_("Palabras clave: tu CV cita {found} de las {total} que pide la oferta ({percent} % ponderado por lo "
                       "que las pide).").format(found=len(estimate.found), total=total,
                                                percent=round(estimate.keyword_score * 100)))
    elif estimate.no_keywords:
        lines.append(_("Palabras clave: no se reconoce ninguna en esta oferta (no parece de tu campo o usa un vocabulario "
                       "que no conozco), así que no se pueden contar y el resultado no pasa del {limit} %.").format(
                           limit=POSSIBLE - 1))
    else:
        lines.append(_("Palabras clave: no se pueden contar, porque la oferta es una ficha resumida."))
    if estimate.title_score is not None:
        lines.append(_("Cargo: {percent} % de las palabras del título de la oferta aparecen en tu CV.").format(
            percent=round(estimate.title_score * 100)))
    lines.append(_("Estructura del CV: {percent} % de las secciones estándar con contenido (la experiencia pesa el "
                   "doble).").format(percent=round(estimate.format_score * 100)))
    if estimate.failed:
        lines.append(_("Requisitos eliminatorios que no cumples: {names}.").format(names=", ".join(
            f"{name} (−{round((1 - factor) * 100)} %)" for name, factor in zip(estimate.failed, estimate.factors,
                                                                            strict=True))))
    else:
        lines.append(_("Requisitos eliminatorios (experiencia, estudios, idiomas): ninguno incumplido."))
    if estimate.unknown:
        lines.append(ngettext("{count} requisito no se puede saber con esta oferta.",
                              "{count} requisitos no se pueden saber con esta oferta.",
                              estimate.unknown).format(count=estimate.unknown))
    for line in lines:
        box.append(_label(_esc(line)))
    if estimate.missing:
        shown = estimate.missing[:MAX_LISTED]
        more = len(estimate.missing) - len(shown)
        text = ", ".join(shown) + (" " + _("y {count} más").format(count=more) if more > 0 else "")
        box.append(_label("<b>" + _esc(_("Palabras clave que tu CV no cita")) + "</b>: " + _esc(text)
                          + "\n<small>" + _esc(_("Añádelas solo si son ciertas en tu caso: en la experiencia o en las "
                                                 "habilidades del perfil.")) + "</small>", margin_top=2))
    source = (_("Se ha leído tu CV base y el CV que subiste.") if estimate.from_upload
              else _("Se ha leído tu CV base (un PDF subido no se lee)."))
    box.append(_label(f"<small><span foreground='{_GREY}'>{_esc(source)}</span></small>", margin_top=2))
    return box
