"""`.env.example` directives, and the two tools that must read them the same way.

Three tools diff `.env` against `.env.example`; they had three different levels
of understanding. `project_doctor.py` knew `one-of`, `secrets-doctor.sh` knew
nothing, so the same file produced different verdicts depending on which doctor
you asked.

`optional` exists for keys a project *declares* but never *requires* — the
multi-LLM keys here are reserved names nothing in this repo reads, documented so
external CLIs pick them up. Warned about on every run, with no edit that would
clear them short of pasting keys you do not use.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import project_doctor as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
DOCTOR_SH = REPO / "skills" / "secrets" / "secrets-doctor.sh"

EXAMPLE = """REQUIRED_KEY=x
#! optional: NICE_TO_HAVE, ALSO_FINE
NICE_TO_HAVE=x
ALSO_FINE=x
#! one-of: PICK_A, PICK_B
PICK_A=x
PICK_B=x
"""


def _project(tmp_path, env_body):
    (tmp_path / ".env.example").write_text(EXAMPLE, encoding="utf-8")
    (tmp_path / ".env").write_text(env_body, encoding="utf-8")
    return tmp_path


def test_optional_keys_are_never_reported(tmp_path):
    p = _project(tmp_path, "REQUIRED_KEY=1\nPICK_A=1\n")
    assert pd.env_gap(p) == []


def test_required_keys_are_still_reported(tmp_path):
    """The marker must not become a way to silence the file around it."""
    p = _project(tmp_path, "PICK_A=1\n")
    assert pd.env_gap(p) == ["REQUIRED_KEY"]


def test_one_of_still_works_alongside_optional(tmp_path):
    p = _project(tmp_path, "REQUIRED_KEY=1\n")
    assert pd.env_gap(p) == ["one of PICK_A|PICK_B"]


def test_setting_an_optional_key_is_not_an_error(tmp_path):
    """Declared-and-set is the normal case for someone who uses that tool."""
    p = _project(tmp_path, "REQUIRED_KEY=1\nNICE_TO_HAVE=1\nPICK_B=1\n")
    assert pd.env_gap(p) == []


# --- the shell caller reaches the shared implementation ---------------------


# Resolve bash to an absolute path and hand THAT to subprocess. Passing the bare
# name lets Windows search System32 first, where WSL's bash.exe stub lives — with
# WSL disabled it answers "Code d'erreur : Bash/0x80070422" in UTF-16, so the
# test sees empty-looking output and fails somewhere unrelated. shutil.which
# uses Python's PATH order and finds Git Bash; CreateProcess does not.
BASH = shutil.which("bash")


@pytest.mark.skipif(not BASH, reason="bash not available")
@pytest.mark.parametrize(
    "env_body,expect_clean",
    [
        ("REQUIRED_KEY=1\nPICK_A=1\n", True),  # optional unset -> fine
        ("PICK_A=1\n", False),  # required missing -> flagged
        ("REQUIRED_KEY=1\n", False),  # one-of unsatisfied -> flagged
    ],
)
def test_secrets_doctor_agrees_with_project_doctor(tmp_path, env_body, expect_clean):
    """Same file, same verdict, whichever doctor you ask.

    This no longer proves two implementations agree — since the extraction there
    is one, and agreement is structural. What it still proves is that the shell
    caller actually reaches it: that the relative path to env_spec.py resolves,
    that uv runs it, and that gap lines are parsed back out and surfaced as
    warnings. Those are the parts that can silently break, and a doctor that
    reports nothing looks identical to a doctor that found nothing.

    Only the key-diff section is compared — secrets-doctor also runs gitleaks and
    inspects git config, which are not this test's subject.
    """
    p = _project(tmp_path, env_body)
    (p / ".gitignore").write_text(".env\n", encoding="utf-8")
    r = subprocess.run(
        [BASH, DOCTOR_SH.as_posix()], cwd=p, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
    )
    marker = "- .env vs .env.example"
    assert marker in r.stdout, f"secrets-doctor produced no key-diff section:\n{r.stdout!r}"
    section = r.stdout.split(marker)[1].split("- gitleaks")[0]
    sh_clean = "missing in .env" not in section
    py_clean = pd.env_gap(p) == []
    assert sh_clean == py_clean == expect_clean, (
        f"disagreement — bash clean={sh_clean}, python clean={py_clean}\n{section}"
    )


def test_the_repos_own_example_declares_its_reserved_names(tmp_path):
    """The multi-LLM keys are reserved names, not requirements. If that marker is
    dropped, every machine that has not pasted four API keys reports four gaps."""
    text = (REPO / ".env.example").read_text(encoding="utf-8", errors="replace")
    declared = {k.strip() for m in pd.OPTIONAL_RE.finditer(text) for k in m.group(1).split(",")}
    for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        assert key in declared, f"{key} is reserved but not marked optional"


# --- the CLI contract the shell depends on ---------------------------------


def _cli(tmp_path, argv):
    import env_spec

    return env_spec.main(argv)


def test_cli_exits_0_when_nothing_is_missing(tmp_path):
    p = _project(tmp_path, "REQUIRED_KEY=1\nPICK_A=1\n")
    assert _cli(tmp_path, ["--dir", str(p)]) == 0


def test_cli_exits_1_and_prints_each_gap(tmp_path, capsys):
    p = _project(tmp_path, "PICK_A=1\n")
    assert _cli(tmp_path, ["--dir", str(p)]) == 1
    assert capsys.readouterr().out.split() == ["REQUIRED_KEY"]


def test_cli_exits_2_when_there_is_nothing_to_compare(tmp_path):
    """Distinct from "no gaps": the shell must not report a clean diff for a
    project that has no .env at all."""
    import env_spec

    (tmp_path / ".env.example").write_text("A=1\n", encoding="utf-8")
    assert _cli(tmp_path, ["--dir", str(tmp_path)]) == env_spec.NOTHING_TO_COMPARE


def test_directive_lines_are_not_parsed_as_keys():
    """`#! one-of: A, B` contains a colon and words but must never become a key."""
    import env_spec

    assert env_spec.declared_keys("#! one-of: A, B\nREAL=1\n") == {"REAL"}
