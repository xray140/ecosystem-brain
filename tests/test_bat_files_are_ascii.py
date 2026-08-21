"""Batch files must be pure ASCII with CRLF endings.

cmd.exe reads a .bat in the OEM codepage, not UTF-8. A single em-dash in a REM
line decoded to mojibake and cmd parsed the remains as a command named "M",
printing "'M' is not recognized" five times per run. The script still worked, so
nothing failed — it just made every scheduled run look broken, which is worse
than failing: it teaches you to ignore the output.

CRLF matters for the same reason. cmd's parser is byte-oriented and an LF-only
.bat mis-splits lines. .gitattributes normalises the repo to LF, so a future
renormalise could silently convert these and break them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BATS = sorted((REPO / "scripts").glob("*.bat"))


def test_there_are_bat_files_to_check():
    """Guard against the globs silently matching nothing."""
    assert BATS, "no .bat files found — did scripts/ move?"


@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_bat_is_pure_ascii(bat):
    raw = bat.read_bytes()
    offenders = [
        (i + 1, line) for i, line in enumerate(raw.split(b"\n")) if any(b > 0x7F for b in line)
    ]
    assert not offenders, (
        f"{bat.name} has non-ASCII on line(s) {[n for n, _ in offenders]} — "
        "cmd.exe reads .bat in the OEM codepage and will mis-parse it"
    )


@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_bat_uses_crlf(bat):
    raw = bat.read_bytes()
    lone_lf = raw.replace(b"\r\n", b"").count(b"\n")
    assert lone_lf == 0, f"{bat.name} has {lone_lf} LF-only line ending(s) — cmd.exe needs CRLF"


@pytest.mark.parametrize("bat", BATS, ids=lambda p: p.name)
def test_bat_has_no_utf8_bom(bat):
    """A BOM lands before `@echo off`, so the first line is never suppressed."""
    assert not bat.read_bytes().startswith(b"\xef\xbb\xbf"), f"{bat.name} starts with a UTF-8 BOM"
