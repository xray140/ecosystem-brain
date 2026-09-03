"""Every text-mode subprocess call must name its encoding.

`text=True` alone decodes the child's bytes with the *locale* encoding. On this
ecosystem's primary platform that is cp1252, while every child here writes
UTF-8 — so an em dash (E2 80 94) came back as three cp1252 characters and was
written straight into the artefact.

That is what happened to the weekly heartbeat: `maintenance.run()` captured its
children in locale text mode, and eight consecutive reports in
memory/maintenance/ carried the wreckage. No check noticed, because the run was
fine — every exit code was 0 and only the artefact was degraded. It is the exact
failure decisions/verification-integrity names, so the fix is a rule that holds
for call sites nobody has written yet, not six patched lines.

The rule is deliberately blunt: text mode implies an explicit
`encoding="utf-8"` AND an explicit `errors=`, even where the call captures
nothing today. A call that decodes nothing is one `capture_output=True` away
from decoding, and that edit should not have to remember this.

`errors=` is not belt-and-braces. Fixing the encoding alone made
`mutate_checks.py` decode strictly, and the first run after that died in a
subprocess reader *thread* on byte 0x97 — a cp1252 em dash from a French-locale
child. All 18 mutants were caught and the harness still exited 1, with the
captured output truncated and nothing saying why. Not every child is ours;
git, gh, npm and the Windows shell all speak the console codepage on occasion.
One replacement character in one line is the cheap outcome.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("scripts", "hooks", "skills", "tests")

# The subprocess entry points that can run in text mode.
SPAWNERS = {"run", "Popen", "check_output", "call", "check_call"}


def _python_files() -> list[Path]:
    files: list[Path] = []
    for d in SOURCE_DIRS:
        files.extend(p for p in (REPO / d).rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def _kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_true(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _spawn_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in SPAWNERS
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "subprocess"
    ]


def _violations() -> list[str]:
    bad: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _spawn_calls(tree):
            text_mode = _is_true(_kwarg(call, "text")) or _is_true(
                _kwarg(call, "universal_newlines")
            )
            if not text_mode:
                continue
            where = f"{path.relative_to(REPO).as_posix()}:{call.lineno}"
            enc = _kwarg(call, "encoding")
            if enc is None:
                bad.append(f"{where} — no encoding=")
            elif not (isinstance(enc, ast.Constant) and enc.value == "utf-8"):
                bad.append(f"{where} — encoding is not 'utf-8'")
            if _kwarg(call, "errors") is None:
                bad.append(f"{where} — no errors= (a stray byte kills the reader thread)")
    return bad


def test_every_text_mode_subprocess_call_names_utf8():
    bad = _violations()
    assert not bad, (
        "text-mode subprocess calls decoding with the locale encoding:\n  " + "\n  ".join(bad)
    )


def test_the_scan_actually_finds_the_calls():
    """A source-scanning test that matches nothing passes for the wrong reason.

    If the walk stops finding call sites — a helper is renamed, an import style
    changes, a directory moves — the rule above goes quietly green while the
    defect it guards is free to come back.
    """
    found = sum(
        len(_spawn_calls(ast.parse(p.read_text(encoding="utf-8")))) for p in _python_files()
    )
    assert found >= 20, f"expected the repo's subprocess call sites, walked only {found}"


# --- the other half: what our own scripts WRITE -----------------------------
# Decoding children as UTF-8 only helps if the children encode as UTF-8. On
# Windows a script whose stdout is a pipe encodes with the locale codepage, so
# `memory-search.py status` sent its em dash as the single byte 0x97 and the
# fixed heartbeat filed it as U+FFFD — the same corruption, entering from the
# other side, and visible in memory/maintenance/2026-09-03.md before this rule
# existed.
#
# selfcheck.py was getting this right by accident: it imports scan_agent, which
# reconfigures stdout at import time, and reconfiguring is process-global. An
# import moving would have taken the encoding with it.

ENTRY_POINT_DIRS = ("scripts", "hooks", "skills")


def _entry_points() -> list[Path]:
    """Scripts meant to be executed, i.e. those with a __main__ block."""
    out = []
    for d in ENTRY_POINT_DIRS:
        for p in (REPO / d).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            for node in tree.body:
                if (
                    isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"
                ):
                    out.append(p)
                    break
    return sorted(out)


def test_every_entry_point_forces_utf8_stdout():
    missing = [
        p.relative_to(REPO).as_posix()
        for p in _entry_points()
        if "sys.stdout.reconfigure" not in p.read_text(encoding="utf-8")
    ]
    assert not missing, (
        "these print through a pipe in the locale encoding:\n  " + "\n  ".join(missing)
    )


def test_the_entry_point_scan_finds_them():
    """Same reason as above: a walk that matches nothing passes for free."""
    found = _entry_points()
    assert len(found) >= 20, f"expected the repo's runnable scripts, found {len(found)}"
