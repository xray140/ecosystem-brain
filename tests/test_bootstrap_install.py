"""Tests for bootstrap's write path — the code that edits the live ~/.claude.

Everything here runs against a temp CLAUDE_DIR. The properties that matter are
the ones a user only discovers when they are already broken: that merging hooks
does not eat their other settings, that --dry-run really writes nothing, and
that an existing .env is never overwritten by the example.
"""

from __future__ import annotations

import json

import pytest

import bootstrap as bs


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    """Point bootstrap's module-level targets at a sandbox."""
    d = tmp_path / "claude"
    monkeypatch.setattr(bs, "CLAUDE_DIR", d)
    monkeypatch.setattr(bs, "SETTINGS", d / "settings.json")
    return d


@pytest.fixture
def hooks_template(tmp_path, monkeypatch):
    p = tmp_path / "hooks.json"
    p.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": f"bash {bs.TOKEN}/x.sh"}]}
                    ]
                },
                "_notes": {"doc": "not wiring"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bs, "HOOKS_TEMPLATE", p)
    return p


# --- merge_settings: the user's other config must survive ------------------
def test_merge_preserves_unrelated_settings(claude_dir, hooks_template):
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"model": "opus", "mcpServers": {"mine": {}}, "hooks": {"old": []}}),
        encoding="utf-8",
    )
    bs.merge_settings(dry=False, bash_root="/c/clone/eco")
    live = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert live["model"] == "opus", "bootstrap must not clobber unrelated keys"
    assert live["mcpServers"] == {"mine": {}}
    assert "SessionStart" in live["hooks"], "hooks replaced, not merged into the old value"
    assert "old" not in live["hooks"]


def test_merge_creates_settings_when_absent(claude_dir, hooks_template):
    bs.merge_settings(dry=False, bash_root="/c/clone/eco")
    live = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert live["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "bash /c/clone/eco/x.sh"
    assert live["permissions"] == bs.PERMISSIONS


def test_merge_writes_the_deny_rules_for_env_files(claude_dir, hooks_template):
    bs.merge_settings(dry=False, bash_root="/c/clone/eco")
    live = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert any(".env" in rule for rule in live["permissions"]["deny"])
    assert any("git push" in rule for rule in live["permissions"]["ask"])


def test_merge_dry_run_writes_nothing(claude_dir, hooks_template, capsys):
    bs.merge_settings(dry=True, bash_root="/c/clone/eco")
    assert not (claude_dir / "settings.json").exists()
    assert "[dry]" in capsys.readouterr().out


def test_settings_are_written_with_lf(claude_dir, hooks_template):
    bs.merge_settings(dry=False, bash_root="/c/clone/eco")
    assert b"\r\n" not in (claude_dir / "settings.json").read_bytes()


# --- copy_tree ------------------------------------------------------------
def test_copy_tree_rewrites_the_token(tmp_path, capsys):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "a.md").write_text(f"run {bs.TOKEN}/scripts/x.py\n", encoding="utf-8")
    bs.copy_tree(src, dst, dry=False, label="commands", bash_root="/c/clone/eco", rewrite=True)
    assert (dst / "a.md").read_text(encoding="utf-8") == "run /c/clone/eco/scripts/x.py\n"


def test_copy_tree_without_rewrite_copies_verbatim(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "a.md").write_text(f"run {bs.TOKEN}/x\n", encoding="utf-8")
    bs.copy_tree(src, dst, dry=False, label="agents", bash_root="/c/clone/eco")
    assert bs.TOKEN in (dst / "a.md").read_text(encoding="utf-8")


def test_copy_tree_writes_lf(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "a.md").write_text(f"{bs.TOKEN}\nsecond line\n", encoding="utf-8")
    bs.copy_tree(src, dst, dry=False, label="commands", bash_root="/root", rewrite=True)
    assert b"\r\n" not in (dst / "a.md").read_bytes()


def test_copy_tree_dry_run_writes_nothing(tmp_path, capsys):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "a.md").write_text("x", encoding="utf-8")
    bs.copy_tree(src, dst, dry=True, label="commands", bash_root="/root")
    assert not dst.exists()
    assert "[dry]" in capsys.readouterr().out


def test_copy_tree_missing_source_is_not_fatal(tmp_path, capsys):
    bs.copy_tree(tmp_path / "nope", tmp_path / "dst", False, "commands", "/root")
    assert "[skip]" in capsys.readouterr().out


# --- seed_env: never overwrite real secrets -------------------------------
def test_existing_env_is_never_overwritten(tmp_path, monkeypatch, capsys):
    """The .env holds real keys. Re-running bootstrap must not touch it."""
    monkeypatch.setattr(bs, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("REAL_KEY=secret\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("REAL_KEY=\n", encoding="utf-8")
    bs.seed_env(dry=False)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "REAL_KEY=secret\n"
    assert "already present" in capsys.readouterr().out


def test_missing_env_is_seeded_from_the_example(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "REPO_ROOT", tmp_path)
    (tmp_path / ".env.example").write_text("KEY=\n", encoding="utf-8")
    bs.seed_env(dry=False)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "KEY=\n"


def test_seed_env_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "REPO_ROOT", tmp_path)
    (tmp_path / ".env.example").write_text("KEY=\n", encoding="utf-8")
    bs.seed_env(dry=True)
    assert not (tmp_path / ".env").exists()


def test_seed_env_without_an_example_is_not_fatal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bs, "REPO_ROOT", tmp_path)
    bs.seed_env(dry=False)
    assert "[skip]" in capsys.readouterr().out


# --- verify_live: catches a moved repo ------------------------------------
def test_verify_flags_hook_scripts_that_no_longer_exist(claude_dir, capsys):
    """The classic breakage: the repo moved and bootstrap was never re-run, so
    every hook silently points at a dead path."""
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": "bash /gone/x.sh"}]}]
                }
            }
        ),
        encoding="utf-8",
    )
    assert bs.verify_live() == 1
    out = capsys.readouterr().out
    assert "[STALE]" in out
    assert "/gone/x.sh" in out


def test_verify_passes_when_every_script_resolves(claude_dir, tmp_path, capsys):
    claude_dir.mkdir()
    real = tmp_path / "real.sh"
    real.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": f"bash {real.as_posix()}"}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    assert bs.verify_live() == 0
    assert "[ok]" in capsys.readouterr().out


def test_verify_without_settings_is_not_a_failure(claude_dir, capsys):
    assert bs.verify_live() == 0
    assert "[skip]" in capsys.readouterr().out


def test_verify_flag_short_circuits_main(claude_dir, capsys):
    assert bs.main(["--verify"]) == 0
    assert "verify:" in capsys.readouterr().out


# --- main: end to end, in a sandbox ---------------------------------------
def test_main_dry_run_leaves_the_claude_dir_untouched(claude_dir, hooks_template, capsys):
    assert bs.main(["--dry-run"]) == 0
    assert not claude_dir.exists()
    assert "dry run — nothing written" in capsys.readouterr().out


def test_main_installs_commands_agents_and_skills(claude_dir, hooks_template, capsys):
    assert bs.main([]) == 0
    out = capsys.readouterr().out
    assert (claude_dir / "settings.json").exists()
    for label in ("commands", "agents", "skills"):
        assert label in out
    # the real repo ships all three, so each copy must have produced files
    assert (claude_dir / "commands" / "ecosystem-brain" / "doctor.md").exists()
    assert (claude_dir / "agents" / "security-auditor.md").exists()
    assert (claude_dir / "skills" / "memory" / "SKILL.md").exists()


def test_installed_files_carry_no_unexpanded_token(claude_dir, hooks_template):
    bs.main([])
    for p in claude_dir.rglob("*.md"):
        assert bs.TOKEN not in p.read_text(encoding="utf-8"), f"{p.name} kept a raw token"


def test_installed_files_point_at_this_clone(claude_dir, hooks_template):
    bs.main([])
    root = bs.to_bash_path(bs.REPO_ROOT)
    doctor_cmd = (claude_dir / "commands" / "ecosystem-brain" / "doctor.md").read_text(
        encoding="utf-8"
    )
    assert root in doctor_cmd
