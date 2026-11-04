import faulthandler
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

from grepleo import logsetup

SRC = str(Path(__file__).resolve().parents[1] / "src")


def run(code: str, log: Path) -> subprocess.CompletedProcess:
    """Un Python aparte (la redirección de la salida de errores no se puede probar dentro de pytest)."""
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {SRC!r})
        from pathlib import Path
        from grepleo import logsetup
        logsetup.install(Path({str(log)!r}), redirect=True)
    """) + textwrap.dedent(code)
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=False)


def test_an_uncaught_exception_and_stderr_output_end_up_in_the_log(tmp_path):
    log = tmp_path / "datos" / "grepleo.log"
    result = run("""
        import sys
        print("aviso de GTK simulado", file=sys.stderr)
        raise RuntimeError("fallo al cerrar")
    """, log)
    assert result.returncode == 1 and "fallo al cerrar" not in result.stderr     # no sale por la salida de errores
    text = log.read_text(encoding="utf-8")
    assert "--- " in text and "Grepleo " in text and "pid " in text
    assert "aviso de GTK simulado" in text and "Traceback" in text and "RuntimeError: fallo al cerrar" in text


def test_sigusr1_dumps_the_threads_of_a_stuck_process_into_the_log(tmp_path):
    log = tmp_path / "grepleo.log"
    result = run("""
        import os, signal
        os.kill(os.getpid(), signal.SIGUSR1)
        import time; time.sleep(0.2)
    """, log)
    assert result.returncode == 0
    assert "most recent call first" in log.read_text(encoding="utf-8")


def test_a_big_log_is_rotated_and_an_unwritable_folder_does_not_stop_the_start(tmp_path):
    log = tmp_path / "grepleo.log"
    log.write_text("x" * (logsetup.MAX_BYTES + 10), encoding="utf-8")
    try:
        assert logsetup.install(log, redirect=False) == log
        assert (tmp_path / "grepleo.log.1").exists() and log.stat().st_size < 1000
    finally:
        faulthandler.disable()                       # que el registro de la prueba no siga activo en pytest
        faulthandler.unregister(signal.SIGUSR1)
    blocker = tmp_path / "archivo"
    blocker.write_text("no es una carpeta", encoding="utf-8")
    assert logsetup.install(blocker / "dentro" / "grepleo.log", redirect=False) is None
