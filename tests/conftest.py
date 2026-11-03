import os
import tempfile

# Las pruebas comprueban los textos en español (el idioma fuente), vengan los .mo compilados o no, y nunca
# tocan los datos reales del usuario: ajustes y base de datos van a una carpeta temporal. Se fija antes de
# importar nada del paquete.
os.environ["LANGUAGE"] = "es"
_home = tempfile.mkdtemp(prefix="grepleo-tests-")
os.environ["HOME"] = _home
os.environ["XDG_CONFIG_HOME"] = os.path.join(_home, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_home, "data")
