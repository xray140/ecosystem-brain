"""A printed remedy must work exactly as printed, from anywhere.

`task_doctor`'s "here is how to fix it" line failed twice in one session on the
machine it was advising:

  1. relative path -> run from a home directory, powershell answers "the
     argument ... does not exist", which reads like a broken script rather than
     a wrong working directory.
  2. no -ExecutionPolicy Bypass -> the Windows default is Restricted, so no
     .ps1 runs at all and it fails UnauthorizedAccess.

INSTALL.md had the flag the whole time. The tool's line did not, and the tool's
line is the one the reader meets at the moment of failure. Documentation being
right elsewhere does not help.
"""

from __future__ import annotations

from pathlib import Path

import task_doctor as td

REPO = Path(__file__).resolve().parent.parent
CMD = td.REGISTER_CMD


def test_the_script_it_names_exists():
    """The path is derived, so this catches a rename or a move."""
    quoted = CMD.split('"')[1]
    assert Path(quoted).is_file(), f"remedy points at a missing file: {quoted}"


def test_the_path_is_absolute():
    """Relative only works if the reader is already standing in the repo."""
    assert Path(CMD.split('"')[1]).is_absolute()


def test_the_path_is_quoted():
    """A clone root containing a space is the common case on Windows — the same
    defect fixed in the hooks in v4.5.3."""
    assert CMD.count('"') == 2, f"script path is not quoted: {CMD}"


def test_execution_policy_is_bypassed():
    """Without it the command cannot run on a stock Windows install."""
    assert "-ExecutionPolicy Bypass" in CMD


def test_install_docs_and_the_tool_agree():
    """These drifted apart: INSTALL.md carried the flag, task_doctor did not.
    Whichever the reader reaches first has to work."""
    install = (REPO / "INSTALL.md").read_text(encoding="utf-8", errors="replace")
    for line in install.splitlines():
        if "register-scheduled-tasks.ps1" in line and "powershell" in line:
            assert "-ExecutionPolicy Bypass" in line, (
                f"INSTALL.md documents an invocation that cannot run: {line.strip()}"
            )


def test_remedy_is_printed_when_a_task_is_failing(monkeypatch, capsys):
    """The wiring, not just the constant."""
    monkeypatch.setattr(
        td, "query_tasks", lambda: [{"Name": "EcosystemBrain-X", "LastResult": 1, "LastRun": ""}]
    )
    assert td.main([]) == 1
    assert CMD in capsys.readouterr().out
