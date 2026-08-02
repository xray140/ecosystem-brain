"""Tests for init_project.apply() — the half that writes to disk.

Every subprocess is stubbed, so nothing scaffolds, installs, or pushes for real.
The property that matters most here is the last one: a scaffold whose baseline
is red must never reach GitHub. `--github` publishing broken code is the one
outcome in this script that is visible to other people.
"""

from __future__ import annotations

import subprocess

import init_project as ip
import pytest


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect the destination, the vault, and every subprocess.

    VAULT is a separate seam from REPO_ROOT: the project card and the MOC follow
    the vault, everything else follows the repo. Conflating them is what made
    `--apply` write into this repo no matter where the project itself landed.
    """
    dest_root = tmp_path / "projects"
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    dest_root.mkdir()
    (repo / "memory" / "projects").mkdir(parents=True)
    (vault / "projects").mkdir(parents=True)
    monkeypatch.setattr(ip, "DEST_ROOT", dest_root)
    monkeypatch.setattr(ip, "REPO_ROOT", repo)
    monkeypatch.setattr(ip, "VAULT", vault)
    monkeypatch.setattr(ip, "PROJECTS_MOC", vault / "projects-moc.md")
    moc_calls: list[tuple] = []
    monkeypatch.setattr(ip, "append_to_moc", lambda n, b: (moc_calls.append((n, b)), True)[1])
    return dest_root, vault, moc_calls


@pytest.fixture
def runs(monkeypatch, sandbox):
    """Record every subprocess and make the scaffold step create its directory."""
    dest_root, _repo, _moc = sandbox
    recorded: list[list[str]] = []
    codes: dict[str, int] = {}

    def fake_run(cmd):
        recorded.append(cmd)
        joined = " ".join(cmd)
        if "scaffold.py" in joined:
            code = codes.get("scaffold", 0)
            if code == 0:
                name = cmd[cmd.index("--name") + 1]
                (dest_root / name).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, code, "", "scaffold blew up")
        if "install-agent.py" in joined:
            return subprocess.CompletedProcess(cmd, codes.get("install", 0), "", "install err")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(ip, "run", fake_run)
    return recorded, codes


def _cfg(build="cli", rigor="product", touches=(), stack=None):
    """A real config from the real profile engine.

    Hand-rolling this dict would let the test drift from whatever `resolve`
    actually produces — which is exactly how it first failed.
    """
    return ip.resolve(ip.load(ip.PROFILES), build, rigor, list(touches), stack)


def _apply(name="demo", cfg=None, resolved=None, **kw):
    opts = {"build": "cli", "api_keys": [], "do_verify": False, "do_github": False}
    opts.update(kw)
    return ip.apply(name, cfg or _cfg(), resolved or [], **opts)


# --- scaffold failure aborts everything -----------------------------------
def test_scaffold_failure_aborts(sandbox, runs, capsys):
    recorded, codes = runs
    codes["scaffold"] = 1
    assert _apply() == 1
    out = capsys.readouterr().out
    assert "scaffold failed" in out
    assert len(recorded) == 1, "nothing may run after the scaffold fails"


# --- what gets written ----------------------------------------------------
def test_tailored_agents_md_is_written(sandbox, runs):
    dest_root, _repo, _moc = sandbox
    _apply("demo")
    text = (dest_root / "demo" / "AGENTS.md").read_text(encoding="utf-8")
    assert "demo" in text
    assert b"\r\n" not in (dest_root / "demo" / "AGENTS.md").read_bytes()


def test_api_keys_are_named_as_placeholders_never_values(sandbox, runs, capsys):
    dest_root, _repo, _moc = sandbox
    _apply("demo", api_keys=["youtube", "tiktok"])
    env = (dest_root / "demo" / ".env.example").read_text(encoding="utf-8")
    assert "YOUTUBE_API_KEY=" in env
    assert "TIKTOK_API_KEY=" in env
    for line in env.splitlines():
        if "=" in line and not line.startswith("#"):
            assert line.endswith("="), f"a value leaked into .env.example: {line!r}"
    assert "named 2 API key(s)" in capsys.readouterr().out


def test_existing_env_example_is_appended_to_not_replaced(sandbox, runs):
    dest_root, _repo, _moc = sandbox
    (dest_root / "demo").mkdir()
    (dest_root / "demo" / ".env.example").write_text("PRIOR=\n", encoding="utf-8")
    _apply("demo", api_keys=["youtube"])
    env = (dest_root / "demo" / ".env.example").read_text(encoding="utf-8")
    assert "PRIOR=" in env and "YOUTUBE_API_KEY=" in env


def test_memory_card_is_written_and_registered(sandbox, runs, capsys):
    _dest, vault, moc_calls = sandbox
    _apply("demo")
    card = vault / "projects" / "demo.md"
    assert card.exists(), "the card follows VAULT, not REPO_ROOT"
    assert b"\r\n" not in card.read_bytes()
    assert moc_calls and moc_calls[0][0] == "demo"
    assert "registered in projects-moc" in capsys.readouterr().out


# --- agent installation ---------------------------------------------------
def test_local_agents_need_no_install(sandbox, runs, capsys):
    recorded, _codes = runs
    _apply(resolved=[{"name": "bug-fixer", "source": "local"}])
    assert not any("install-agent.py" in " ".join(c) for c in recorded)
    assert "already available" in capsys.readouterr().out


def test_github_agents_go_through_the_scanning_installer(sandbox, runs, capsys):
    recorded, _codes = runs
    _apply(resolved=[{"name": "python-pro", "source": "github", "repo": "u/r", "path": "a.md"}])
    installer = next(c for c in recorded if "install-agent.py" in " ".join(c))
    assert "--repo" in installer and "u/r" in installer
    assert "installed + scanned" in capsys.readouterr().out


def test_blocked_agent_is_reported_and_not_counted(sandbox, runs, capsys):
    _recorded, codes = runs
    codes["install"] = 2
    rc = _apply(resolved=[{"name": "evil", "source": "github", "repo": "u/r", "path": "a.md"}])
    out = capsys.readouterr().out
    assert rc == 0, "one blocked agent does not fail the whole init"
    assert "[BLOCKED] evil" in out
    assert "0/1 agents ready" in out


def test_install_error_is_distinguished_from_a_block(sandbox, runs, capsys):
    _recorded, codes = runs
    codes["install"] = 1
    _apply(resolved=[{"name": "flaky", "source": "github", "repo": "u/r", "path": "a.md"}])
    assert "[error]   flaky" in capsys.readouterr().out


# --- the green-baseline gate ----------------------------------------------
def test_red_baseline_fails_the_run(sandbox, runs, monkeypatch, capsys):
    monkeypatch.setattr(ip, "verify_baseline", lambda dest, template: False)
    assert _apply(do_verify=True) == 1
    assert "green baseline FAILED" in capsys.readouterr().out


def test_green_baseline_returns_zero(sandbox, runs, monkeypatch):
    monkeypatch.setattr(ip, "verify_baseline", lambda dest, template: True)
    assert _apply(do_verify=True) == 0


def test_no_verify_skips_the_baseline(sandbox, runs, monkeypatch):
    monkeypatch.setattr(ip, "verify_baseline", lambda d, t: pytest.fail("baseline must not run"))
    assert _apply(do_verify=False) == 0


# --- never publish broken code --------------------------------------------
def test_red_baseline_blocks_the_github_push(sandbox, runs, monkeypatch, capsys):
    """The one outcome here that other people can see."""
    monkeypatch.setattr(ip, "verify_baseline", lambda dest, template: False)
    monkeypatch.setattr(ip, "gh_publish", lambda *a, **k: pytest.fail("must not push"))
    assert _apply(do_verify=True, do_github=True) == 1
    assert "not pushing broken code" in capsys.readouterr().out


def test_green_baseline_allows_the_push(sandbox, runs, monkeypatch):
    pushed = []
    monkeypatch.setattr(ip, "verify_baseline", lambda dest, template: True)
    monkeypatch.setattr(ip, "gh_publish", lambda name, dest, *a, **k: pushed.append(name))
    _apply(do_verify=True, do_github=True)
    assert pushed == ["demo"]


# --- verify_baseline itself -----------------------------------------------
def test_verify_baseline_fails_on_a_failing_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        ip.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, "", "2 tests failed"),
    )
    assert ip.verify_baseline(tmp_path, "python-project") is False
    assert "[FAIL]" in capsys.readouterr().out


def test_verify_baseline_passes_when_all_commands_succeed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ip.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0, "ok", "")
    )
    assert ip.verify_baseline(tmp_path, "python-project") is True


def test_verify_baseline_skips_an_unknown_template(tmp_path, capsys):
    assert ip.verify_baseline(tmp_path, "no-such-template") is True
    assert "[skip]" in capsys.readouterr().out


# --- append_to_moc (its own seam) -----------------------------------------
def test_moc_entry_is_added_once(tmp_path):
    moc = tmp_path / "projects-moc.md"
    assert ip.append_to_moc("demo", "cli · python", moc=moc) is True
    assert ip.append_to_moc("demo", "cli · python", moc=moc) is False, "must be idempotent"
    assert moc.read_text(encoding="utf-8").count("[[demo]]") == 1


def test_moc_is_created_with_a_header_when_absent(tmp_path):
    moc = tmp_path / "nested" / "projects-moc.md"
    ip.append_to_moc("demo", "cli", moc=moc)
    text = moc.read_text(encoding="utf-8")
    assert text.startswith("---\ntype: moc")
    assert "[[demo]]" in text
    assert b"\r\n" not in moc.read_bytes()


def test_moc_keeps_existing_entries(tmp_path):
    moc = tmp_path / "projects-moc.md"
    ip.append_to_moc("first", "cli", moc=moc)
    ip.append_to_moc("second", "web", moc=moc)
    text = moc.read_text(encoding="utf-8")
    assert "[[first]]" in text and "[[second]]" in text


# --- gh_publish -----------------------------------------------------------
def test_publish_skips_without_the_gh_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ip.shutil, "which", lambda x: None)
    assert ip.gh_publish("demo", tmp_path) is False
    assert "gh CLI not found" in capsys.readouterr().out


def test_publish_reports_a_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ip.shutil, "which", lambda x: "/usr/bin/gh")
    monkeypatch.setattr(
        ip, "run", lambda cmd: subprocess.CompletedProcess([], 1, "", "repo already exists")
    )
    assert ip.gh_publish("demo", tmp_path) is False
    assert "repo already exists" in capsys.readouterr().out


def test_publish_defaults_to_private(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ip.shutil, "which", lambda x: "/usr/bin/gh")
    monkeypatch.setattr(ip, "run", lambda cmd: subprocess.CompletedProcess([], 0, "", ""))
    assert ip.gh_publish("demo", tmp_path) is True
    assert "private" in capsys.readouterr().out


# --- sandboxability: why this path went unexercised ----------------------
# `--apply` wrote a memory card, a MOC line and a registry mutation into THIS
# repo no matter what, so running the flagship command even once dirtied it.
# That is why it was never in CI, and why a Windows crash in its own baseline
# step (bare `npm` raising FileNotFoundError) survived until 2026-08-02.


def test_vault_is_redirectable_by_env(tmp_path):
    """ECOSYSTEM_VAULT exists for the same reason ECOSYSTEM_DEST_ROOT does.

    Asserted by re-running the module's own resolution rather than
    `importlib.reload`: reloading mutates the shared module in place, and the
    first draft of this test leaked a `demo.md` into the real vault when a later
    test ran against the restored constants.
    """
    from pathlib import Path

    env = {"ECOSYSTEM_VAULT": str(tmp_path / "elsewhere")}
    resolved = Path(env.get("ECOSYSTEM_VAULT") or ip.REPO_ROOT / "memory")
    assert resolved == tmp_path / "elsewhere"
    # and the default, with nothing set
    assert Path({}.get("ECOSYSTEM_VAULT") or ip.REPO_ROOT / "memory") == ip.REPO_ROOT / "memory"


def test_the_shipped_default_vault_is_the_repo_vault():
    assert ip.VAULT == ip.REPO_ROOT / "memory"
    assert ip.PROJECTS_MOC == ip.VAULT / "projects-moc.md"


def test_append_to_moc_resolves_the_target_at_call_time(monkeypatch, tmp_path):
    """A default argument would bind PROJECTS_MOC at import — the exact trap
    that made project_doctor's load_cards audit the real vault from a test."""
    moc = tmp_path / "late-bound.md"
    monkeypatch.setattr(ip, "PROJECTS_MOC", moc)
    assert ip.append_to_moc("demo", "cli") is True
    assert moc.exists(), "must write where PROJECTS_MOC points NOW"


def test_skip_agents_touches_no_registry(sandbox, runs, capsys):
    """The half that cannot be redirected by env: agent installs mutate
    registry/installed.json and ~/.claude. --skip-agents excludes them so the
    rest of --apply is exercisable."""
    recorded, _codes = runs
    rc = _apply(
        resolved=[{"name": "python-pro", "source": "github", "repo": "u/r", "path": "a.md"}],
        skip_agents=True,
    )
    assert rc == 0
    assert not any("install-agent.py" in " ".join(c) for c in recorded)
    assert "--skip-agents" in capsys.readouterr().out


def test_without_the_flag_agents_are_still_installed(sandbox, runs):
    recorded, _codes = runs
    _apply(resolved=[{"name": "python-pro", "source": "github", "repo": "u/r", "path": "a.md"}])
    assert any("install-agent.py" in " ".join(c) for c in recorded)


def test_the_indexer_is_pointed_at_the_overridden_vault(sandbox, runs, monkeypatch, tmp_path):
    """Refreshing the manifest must follow the vault, or --apply reindexes the
    real one while writing its card to the sandbox."""
    recorded, _codes = runs
    monkeypatch.setattr(ip, "VAULT", tmp_path / "sandbox-vault")
    _apply(skip_agents=True)
    indexer = next(c for c in recorded if "memory-index.py" in " ".join(c))
    assert "--vault" in indexer
    assert str(tmp_path / "sandbox-vault") in indexer
