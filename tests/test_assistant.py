import pytest

from grepleo import settings
from grepleo.assistant import (
    DEFAULT_COMMAND,
    OUTPUT_NAME,
    PROMPT,
    build_argv,
    build_prompt,
    folder_name,
    prepare_workspace,
    shell_argv,
)
from grepleo.matching import evaluate
from grepleo.models import Job
from grepleo.profiles import Profile


def test_the_command_template_is_split_and_the_prompt_substituted():
    assert build_argv("claude {prompt}", "hola mundo") == ["claude", "hola mundo"]
    assert build_argv("opencode --prompt {prompt}", "x") == ["opencode", "--prompt", "x"]
    assert build_argv('codex --model "gpt 5" {prompt}', "p") == ["codex", "--model", "gpt 5", "p"]
    with pytest.raises(ValueError):
        build_argv("   ", "p")


def test_the_shell_wrapper_runs_the_command_from_an_interactive_shell(monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert shell_argv(["claude", "dos palabras"]) == ["/bin/zsh", "-ic", "exec claude 'dos palabras'"]
    monkeypatch.delenv("SHELL")
    assert shell_argv(["x"])[0] == "/bin/bash"


def test_the_prompt_names_the_files_and_mentions_the_upload_only_when_there_is_one():
    plain = build_prompt(PROMPT, "oferta.md", "cv-base.md")
    assert "@oferta.md" in plain and "@cv-base.md" in plain and f"archivo {OUTPUT_NAME}" in plain
    assert "{" not in plain and "original" not in plain and "cv-subido" not in plain
    with_upload = build_prompt(PROMPT, "oferta.md", "cv-base.md", "cv-subido.pdf")
    assert "@cv-subido.pdf" in with_upload
    assert build_prompt("   ", "o", "c") == build_prompt(PROMPT, "o", "c")        # un mensaje vacío usa el de serie
    assert build_prompt("Usa {offer} y {cv}{upload}. Guarda en {output}", "a.md", "b.md") == \
        "Usa a.md y b.md. Guarda en cv-adaptado.md"


def test_the_workspace_has_only_what_the_assistant_needs_and_keeps_previous_results(tmp_path):
    job = Job(key="infojobs:abc/1", source="infojobs", title="DevOps", description="AWS " * 50, full_description=True)
    profile = Profile(name="p", full_name="Ana", must=["AWS"])
    upload = tmp_path / "mi cv.PDF"
    upload.write_bytes(b"%PDF-1.4 falso")
    profile.cv_file = str(upload)
    base = tmp_path / "cv"
    work = prepare_workspace(base, job, evaluate(job, profile), profile)
    assert work.folder == base / "infojobs-abc-1"
    assert sorted(path.name for path in work.folder.iterdir()) == ["cv-base.md", "cv-subido.pdf", "oferta.md"]
    assert (work.folder / "cv-subido.pdf").read_bytes() == b"%PDF-1.4 falso" and work.upload == "cv-subido.pdf"
    assert "# Ana" in (work.folder / "cv-base.md").read_text(encoding="utf-8")
    (work.folder / OUTPUT_NAME).write_text("resultado anterior", encoding="utf-8")
    profile.cv_file = ""                                           # ya no hay CV subido
    again = prepare_workspace(base, job, evaluate(job, profile), profile)
    names = sorted(path.name for path in again.folder.iterdir())
    assert again.upload == "" and "cv-subido.pdf" not in names and OUTPUT_NAME not in names
    assert any(name.startswith("cv-adaptado-") for name in names)   # lo anterior queda apartado, no se pierde
    assert folder_name("///") == "oferta" and folder_name("a b:c") == "a-b-c"


def test_assistant_settings_default_to_the_built_in_ones_and_do_not_freeze_the_default_prompt(tmp_path):
    path = tmp_path / "settings.json"
    assert settings.assistant_command(path) == DEFAULT_COMMAND and settings.assistant_prompt(path) == PROMPT
    settings.set_assistant("codex {prompt}", "Otro mensaje {offer}", path)
    assert settings.assistant_command(path) == "codex {prompt}" and settings.assistant_prompt(path) == "Otro mensaje {offer}"
    settings.set_assistant("  ", PROMPT, path)
    assert settings.assistant_command(path) == DEFAULT_COMMAND
    assert '"assistant_prompt": ""' in path.read_text(encoding="utf-8")      # el de serie no se congela
    path.write_text('{"assistant": 5, "assistant_prompt": ["x"]}', encoding="utf-8")
    assert settings.assistant_command(path) == DEFAULT_COMMAND and settings.assistant_prompt(path) == PROMPT
