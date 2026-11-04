"""Ventana de Preferencias: idioma, tema, token de Apify (en el llavero) y gasto máximo por búsqueda."""
import subprocess
from threading import Thread

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .. import secrets, settings
from ..assistant import PROMPT, build_argv
from ..i18n import _
from ..sources.apify import ApifyError, account_info
from .common import labeled

# Los nombres de idioma no se traducen (convención habitual en selectores de idioma):
# «English» se ve igual con la app en español, y viceversa.
LANGUAGE_CODES: list[str | None] = [None, "es", "en"]
THEME_VALUES: list[bool | None] = [None, False, True]   # Sistema, Claro, Oscuro (valor de dark_mode)


def language_labels() -> list[str]:
    return [_("Sistema"), "Español", "English"]


class PreferencesWindow(Gtk.Window):
    """Idioma y tema se aplican reiniciando la aplicación: los textos ya están fijados en los widgets y, en
    Cinnamon/Mint, cambiar gtk-theme-name en caliente no repinta la ventana."""

    def __init__(self, application: Gtk.Application, busy: bool) -> None:
        super().__init__(title=_("Preferencias"), transient_for=application.props.active_window,
                         modal=True, resizable=True)
        self.set_default_size(640, 760)
        self._application = application
        self._busy = busy
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=16,
                      margin_bottom=16, margin_start=16, margin_end=16)
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_child(box)
        self.set_child(scrolled)

        self._language = Gtk.DropDown.new_from_strings(language_labels())
        self._language.set_selected(LANGUAGE_CODES.index(settings.language()))
        box.append(labeled(_("Idioma"), self._language))

        self._theme = Gtk.DropDown.new_from_strings([_("Sistema"), _("Claro"), _("Oscuro")])
        self._theme.set_selected(THEME_VALUES.index(settings.dark_mode()))
        box.append(labeled(_("Tema"), self._theme))

        self._token = Gtk.PasswordEntry(show_peek_icon=True, width_chars=40,
                                        placeholder_text=_("Pega aquí tu token de Apify"))
        self._token_status = Gtk.Label(xalign=0, wrap=True)
        self._token_status.add_css_class("dim-label")
        try:
            self._has_token = secrets.get_token() is not None
            self._token_status.set_text(_("Hay un token guardado en el llavero.") if self._has_token
                                        else _("Todavía no hay ningún token guardado."))
        except secrets.SecretsError as error:
            self._has_token = False
            self._token_status.set_text(_("No hay un llavero disponible: {error}").format(error=error))
        token_box = labeled(_("Token de Apify (se guarda en el llavero del sistema)"), self._token)
        token_box.append(self._token_status)
        checks = Gtk.Box(spacing=8)
        self._check = Gtk.Button(label=_("Comprobar conexión"))
        self._check.connect("clicked", self._on_check)
        forget = Gtk.Button(label=_("Olvidar el token"))
        forget.connect("clicked", self._on_forget)
        checks.append(self._check)
        checks.append(forget)
        token_box.append(checks)
        box.append(token_box)

        self._budget = Gtk.SpinButton.new_with_range(0.1, 50.0, 0.1)
        self._budget.set_value(settings.budget_usd())
        box.append(labeled(_("Gasto máximo por búsqueda en Apify (dólares)"), self._budget))

        box.append(Gtk.Separator())
        intro = Gtk.Label(xalign=0, wrap=True, label=_(
            "Asistente de IA (botón «Adaptar CV»): comando que se abre en un terminal con tu propia sesión. "
            "{{prompt}} se sustituye por el mensaje. Ejemplos: «claude {{prompt}}», «codex {{prompt}}», "
            "«opencode --prompt {{prompt}}».").format())
        box.append(intro)
        self._assistant = Gtk.Entry(text=settings.assistant_command())
        box.append(self._assistant)
        box.append(Gtk.Label(xalign=0, wrap=True, label=_(
            "Mensaje que sustituye a {{prompt}}. Dentro puedes usar {{offer}} (la oferta), {{cv}} (tu CV base), "
            "{{upload}} (tu CV subido, si lo hay) y {{output}} (el archivo que debe crear):").format()))
        self._prompt = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, top_margin=6, bottom_margin=6, left_margin=8,
                                    right_margin=8)
        self._prompt.get_buffer().set_text(settings.assistant_prompt())
        prompt_scroll = Gtk.ScrolledWindow(min_content_height=170, has_frame=True)
        prompt_scroll.set_child(self._prompt)
        box.append(prompt_scroll)
        reset = Gtk.Button(label=_("Restablecer el mensaje"), halign=Gtk.Align.START,
                           tooltip_text=_("Vuelve al mensaje que trae la aplicación"))
        reset.connect("clicked", lambda _button: self._prompt.get_buffer().set_text(PROMPT))
        box.append(reset)
        self._assistant_info = Gtk.Label(xalign=0, wrap=True)
        self._assistant_info.add_css_class("error")
        box.append(self._assistant_info)

        hint = Gtk.Label(label=_("El idioma y el tema se aplican reiniciando la aplicación."), xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        box.append(hint)

        self._apply = Gtk.Button(label=_("Guardar"))
        self._apply.add_css_class("suggested-action")
        self._apply.connect("clicked", self._on_apply)
        box.append(self._apply)

    # --- token ---------------------------------------------------------------------------------------
    def _typed_or_saved_token(self) -> str:
        typed = self._token.get_text().strip()
        if typed:
            return typed
        try:
            return secrets.get_token() or ""
        except secrets.SecretsError:
            return ""

    def _on_check(self, _button: Gtk.Button) -> None:
        token = self._typed_or_saved_token()
        if not token:
            self._token_status.set_text(_("Introduce un token de Apify."))
            return
        self._check.set_sensitive(False)
        self._token_status.set_text(_("Comprobando…"))

        def work() -> None:
            try:
                info = account_info(token)
                text = _("Conectado como {user} (plan {plan}).").format(user=info["username"], plan=info["plan"])
            except ApifyError as error:
                text = str(error)
            GLib.idle_add(self._checked, text)

        Thread(target=work, daemon=True).start()

    def _checked(self, text: str) -> None:
        self._token_status.set_text(text)
        self._check.set_sensitive(True)

    def _on_forget(self, _button: Gtk.Button) -> None:
        try:
            secrets.clear_token()
            self._token_status.set_text(_("Token borrado del llavero."))
        except secrets.SecretsError as error:
            self._token_status.set_text(str(error))

    # --- guardar --------------------------------------------------------------------------------------
    def _on_apply(self, _button: Gtk.Button) -> None:
        typed = self._token.get_text().strip()
        if typed:
            try:
                secrets.set_token(typed)
            except secrets.SecretsError as error:
                self._token_status.set_text(_("No se pudo guardar el token: {error}").format(error=error))
                return
        command = self._assistant.get_text().strip()
        try:
            build_argv(command, "prueba")
        except ValueError as error:
            self._assistant_info.set_text(_("Comando no válido: {error}").format(error=error))
            return
        buffer = self._prompt.get_buffer()
        settings.set_assistant(command, buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False))
        config = settings.read_settings()
        language = LANGUAGE_CODES[self._language.get_selected()]
        dark = THEME_VALUES[self._theme.get_selected()]
        restart = language != settings.language() or dark != settings.dark_mode()
        if restart and self._busy:
            self._token_status.set_text(_("Hay una búsqueda en marcha: espera a que termine para cambiar el idioma o el tema."))
            return
        config["language"] = language
        config["dark_mode"] = dark
        config["budget_usd"] = round(self._budget.get_value(), 2)
        settings.write_settings(config)
        if not restart:
            self.close()
            return
        # Un exec en el sitio conservaría los descriptores abiertos (y con ellos el registro D-Bus de
        # esta instancia): el proceso nuevo se vería como secundario y se cerraría sin ventana. Se
        # lanza un proceso aparte y se cierra este. El ejecutable se toma de /proc/self/exe, no de
        # sys.executable, porque el lanzador instalado usa «exec -a» y eso engaña a sys.executable.
        subprocess.Popen(["/proc/self/exe", "-m", "grepleo"], start_new_session=True)
        self._application.quit()
