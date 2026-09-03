"""The git hooks gate commits made outside Claude Code.

AGENTS.md says "gitleaks gates commits". That was only true inside Claude Code,
whose PreToolUse hook fires on its own Bash calls — `git commit` from a terminal,
VS Code, or another assistant ran nothing. Gemini CLI and Codex are both in use
here and neither reads Claude Code's hook config.

These tests exercise the hook scripts directly rather than through a real commit,
so they do not depend on gitleaks' rule set. That matters: the first manual test
of this hook used AWS's documented example keys, which gitleaks allowlists, and
the commit sailed through — the hook was fine, the fixture was not.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import bootstrap as bs

REPO = Path(__file__).resolve().parent.parent
HOOK_DIR = REPO / "hooks" / "git"
ZERO = "0" * 40
SHA = "a" * 40

pytestmark = pytest.mark.skipif(not shutil.which("bash"), reason="bash not available")
BASH = shutil.which("bash")
GIT = shutil.which("git")


def _path_without(*tools: str) -> str:
    """A PATH that keeps git but drops the named tools.

    Emptying PATH entirely is not a faithful simulation: git is what invokes a
    git hook, so it is definitionally present. Removing it made the hook die at
    `git rev-parse` with exit 127, which tested nothing about the branch under
    test.
    """
    keep = [str(Path(GIT).parent)] if GIT else []
    return os.pathsep.join(keep)


def _run(hook: str, stdin: str = "", path: str | None = None, timeout: int = 60):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [BASH, (HOOK_DIR / hook).as_posix(), "origin", "https://example.invalid"],
        input=stdin,
        cwd=REPO,
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        env=env,
        timeout=timeout,
    )


# --- they exist and can actually run ---------------------------------------


@pytest.mark.parametrize("hook", ["pre-commit", "pre-push"])
def test_hook_exists_and_has_a_shebang(hook):
    p = HOOK_DIR / hook
    assert p.is_file(), f"{hook} is missing"
    assert p.read_text(encoding="utf-8").startswith("#!"), f"{hook} has no shebang"


@pytest.mark.parametrize("hook", ["pre-commit", "pre-push"])
def test_hook_is_executable_in_git(hook):
    """Git must record mode 100755, not just the filesystem.

    core.filemode is false on Windows, so the first commit of these hooks stored
    them 100644 despite bootstrap having chmod'd them locally. A clone on
    Linux/macOS would then check out non-executable hooks — and git SKIPS a
    non-executable hook silently, which is indistinguishable from one that ran
    and passed. Read from the index rather than the filesystem so the assertion
    means the same thing on every platform.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-s", f"hooks/git/{hook}"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    ).stdout
    assert out.strip(), f"hooks/git/{hook} is not tracked"
    mode = out.split()[0]
    assert mode == "100755", (
        f"hooks/git/{hook} is recorded {mode}; git skips a non-executable hook "
        "silently. Fix: git update-index --chmod=+x hooks/git/" + hook
    )


def test_bootstrap_points_git_at_the_tracked_hook_dir():
    """Not copied into .git/hooks: that is untracked, so copies drift and a pull
    carrying a fixed hook would never apply."""
    assert bs.GIT_HOOKS_DIR == HOOK_DIR
    configured = subprocess.run(
        ["git", "-C", str(REPO), "config", "--get", "core.hooksPath"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    assert configured, "core.hooksPath is not set — run scripts/bootstrap.py"
    assert Path(configured).resolve() == HOOK_DIR.resolve()


# --- pre-commit: fail closed -----------------------------------------------


def test_pre_commit_refuses_when_gitleaks_is_absent():
    """The Claude Code hook skips when gitleaks is missing because CI still
    scans. That reasoning does not hold here: CI scans *after* the push, by which
    time the secret is on GitHub. So this one fails closed."""
    r = _run("pre-commit", path=_path_without("gitleaks"))
    assert r.returncode == 1
    assert "gitleaks is not installed" in r.stderr
    assert "--no-verify" in r.stderr, "a refusal must name its override"


def test_pre_commit_names_an_install_command():
    """A gate that blocks without saying how to satisfy it is the failure mode
    this repo spent 2026-08-21 removing."""
    text = (HOOK_DIR / "pre-commit").read_text(encoding="utf-8")
    assert "winget install" in text or "brew install" in text


# --- pre-push: skip what needs no checking ---------------------------------


def test_pre_push_skips_a_ref_deletion():
    """`git push --delete` sends an all-zero local sha. There is no tree to
    verify, and selfcheck would still cost ~20s."""
    r = _run("pre-push", stdin=f"refs/heads/x {ZERO} refs/heads/x {SHA}\n")
    assert r.returncode == 0
    assert "selfcheck" not in r.stdout, "ran the suite for a deletion"


def test_pre_push_skips_when_there_is_nothing_on_stdin():
    r = _run("pre-push", stdin="")
    assert r.returncode == 0


def test_pre_push_verifies_a_real_push():
    """Reaches the selfcheck call for a non-zero sha. PATH is stripped so the
    run stops at the uv lookup — this asserts the control flow, not the suite,
    which the pytest step already runs."""
    r = _run(
        "pre-push",
        stdin=f"refs/heads/master {SHA} refs/heads/master {SHA}\n",
        path=_path_without("uv"),
    )
    assert r.returncode == 1
    assert "uv is not installed" in r.stderr
    assert "--no-verify" in r.stderr


def test_a_mixed_push_is_not_treated_as_a_deletion():
    """One deleted ref alongside one real ref must still verify."""
    stdin = f"refs/heads/x {ZERO} refs/heads/x {SHA}\nrefs/heads/y {SHA} refs/heads/y {SHA}\n"
    r = _run("pre-push", stdin=stdin, path=_path_without("uv"))
    assert r.returncode == 1, "a real ref in the batch must still be checked"
