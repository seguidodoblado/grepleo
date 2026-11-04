import os


def main() -> None:
    from . import i18n, settings

    # El idioma de Preferencias manda; con «Sistema» se recupera el $LANGUAGE original
    # (los reinicios lo heredan, así que se guarda aparte la primera vez).
    original = os.environ.setdefault("GREPLEO_SYSTEM_LANGUAGE", os.environ.get("LANGUAGE", ""))
    chosen = settings.language() or original
    if chosen:
        os.environ["LANGUAGE"] = chosen
    else:
        os.environ.pop("LANGUAGE", None)
    i18n.install()
    from . import logsetup
    logsetup.install()   # antes de cargar GTK: así también quedan sus avisos
    from .ui.gui import run_gui
    run_gui()


if __name__ == "__main__":
    main()
