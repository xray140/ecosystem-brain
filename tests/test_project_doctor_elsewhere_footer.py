"""The `elsewhere` footer must not ask for what the card already has.

A card reaches the `elsewhere` branch only because it carries `host:`. The
footer used to answer that by advising "Add `host: <machine>` to those cards" —
advice addressed to precisely the cards that had already taken it, with no
action that would make it stop. A nag you cannot satisfy is one you learn to
skip, and the footer is where the real failures are summarised.
"""

from __future__ import annotations

import project_doctor as pd

CARD = """---
type: project
status: active
created: 2026-07-13
host: SomeOtherPC
tags: [project]
---
# pinned-elsewhere

## Paths
- Project: `C:\\Users\\someone\\pinned-elsewhere`
"""


def _run(tmp_path, monkeypatch, capsys):
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    (projects / "pinned-elsewhere.md").write_text(CARD, encoding="utf-8")
    monkeypatch.setattr(pd, "VAULT_PROJECTS", projects)
    monkeypatch.setattr(pd, "HOST", "ThisPC")
    pd.main([])
    return capsys.readouterr().out


def test_footer_does_not_ask_for_a_host_the_card_already_has(tmp_path, monkeypatch, capsys):
    out = _run(tmp_path, monkeypatch, capsys)
    assert "elsewhere: SomeOtherPC" in out
    assert "Add `host:" not in out, "footer asks for what put the card in this branch"


def test_pinned_elsewhere_is_reported_but_not_a_failure(tmp_path, monkeypatch, capsys):
    """The count in the footer and the exit status must agree: a project living
    on another machine is information, not something to fix."""
    out = _run(tmp_path, monkeypatch, capsys)
    assert "1 project(s) are pinned to another machine" in out
    assert "need attention" not in out
