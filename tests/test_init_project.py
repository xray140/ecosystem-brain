"""Tests for the /ecosystem-brain:init engine — answer resolution + composition.

These exercise the same functions selfcheck smoke-tests, but assert behavior
(dedup, security injection, package slugging, AGENTS.md content) rather than
just "doesn't raise".
"""

from __future__ import annotations

import pytest

import init_project as ip


@pytest.fixture(scope="module")
def profiles() -> dict:
    return ip.load(ip.PROFILES)


# --- to_package ----------------------------------------------------------
@pytest.mark.parametrize(
    "name, expected",
    [
        ("betting-tracker", "betting_tracker"),
        ("Foo Bar", "foo_bar"),
        ("my.tool", "my_tool"),
        ("123abc", "pkg_123abc"),  # cannot start with a digit
        ("!!!", "pkg"),  # nothing usable
    ],
)
def test_to_package(name, expected):
    assert ip.to_package(name) == expected


# --- resolve -------------------------------------------------------------
def test_resolve_sets_template_from_build(profiles):
    cfg = ip.resolve(profiles, "cli", "product", ["none"], None)
    assert cfg["template"] == profiles["build_types"]["cli"]["template"]


def test_resolve_dedupes_agents(profiles):
    cfg = ip.resolve(profiles, "web", "production", ["api-keys", "money"], "react")
    assert len(cfg["agents"]) == len(set(cfg["agents"])), "agent list has duplicates"


def test_resolve_injects_security_for_sensitive_touches(profiles):
    cfg = ip.resolve(profiles, "api", "product", ["money"], None)
    assert cfg["security"], "money-handling project should carry security rules"


def test_sensitive_touch_adds_more_security_than_none(profiles):
    none_cfg = ip.resolve(profiles, "api", "product", ["none"], None)
    money_cfg = ip.resolve(profiles, "api", "product", ["money"], None)
    assert len(money_cfg["security"]) > len(none_cfg["security"])
    assert any("amount" in r.lower() or "money" in r.lower() for r in money_cfg["security"])


# --- classify_agents -----------------------------------------------------
def test_classify_splits_local_github_dropped(profiles):
    local = profiles.get("local_agents", [])
    assert local, "fixture expects at least one local agent in profiles"
    names = [local[0], "this-agent-does-not-exist-xyz"]
    resolved, dropped = ip.classify_agents(names, profiles)
    sources = {r["name"]: r["source"] for r in resolved}
    assert sources.get(local[0]) == "local"
    assert "this-agent-does-not-exist-xyz" in dropped


def test_classify_github_agent_carries_repo_and_path(profiles):
    catalog = ip.load(ip.CATALOG)["agents"]
    sample = catalog[0]["name"]
    resolved, _ = ip.classify_agents([sample], profiles)
    entry = next(r for r in resolved if r["name"] == sample)
    assert entry["source"] == "github"
    assert entry["repo"] and entry["path"]


# --- compose_agents_md ---------------------------------------------------
def test_compose_includes_name_and_package(profiles):
    cfg = ip.resolve(profiles, "cli", "product", ["none"], None)
    md = ip.compose_agents_md("my-tool", cfg)
    assert "# my-tool — agent operating rules" in md
    assert "my_tool" in md  # package slug substituted into key_files
    assert "## Stack" in md and "## Key files" in md


def test_compose_adds_security_section_when_sensitive(profiles):
    cfg = ip.resolve(profiles, "api", "production", ["pii", "money"], None)
    md = ip.compose_agents_md("secure-svc", cfg)
    assert "## Security" in md


def test_memory_card_has_real_created_date(profiles):
    # Regression: the composer used to emit a literal `created: see-git`
    # placeholder, which leaked into real project cards twice.
    cfg = ip.resolve(profiles, "cli", "product", ["none"], None)
    card = ip.memory_card("demo", cfg, [{"name": "test-writer"}])
    assert "see-git" not in card
    assert "created: 20" in card  # real ISO date


# --- Gap 4: named API keys -----------------------------------------------
@pytest.mark.parametrize(
    "name, expected",
    [
        ("youtube", "YOUTUBE_API_KEY"),
        ("YOUTUBE_API_KEY", "YOUTUBE_API_KEY"),  # already a key, unchanged
        ("stripe secret", "STRIPE_SECRET"),  # ends in SECRET, no _API_KEY suffix
        ("tik-tok", "TIK_TOK_API_KEY"),
        ("  ", ""),
    ],
)
def test_env_key_normalization(name, expected):
    assert ip.env_key(name) == expected


def test_env_block_composes_placeholders_and_dedupes():
    block = ip.env_block(["youtube", "youtube", "tiktok"])
    assert "YOUTUBE_API_KEY=" in block
    assert "TIKTOK_API_KEY=" in block
    assert block.count("YOUTUBE_API_KEY=") == 1  # deduped
    assert "real values go in .env" in block


def test_env_block_empty_for_no_names():
    assert ip.env_block([]) == ""
    assert ip.env_block(["   "]) == ""


# --- Gap 2: verified green baseline --------------------------------------
def test_verify_commands_per_template():
    assert ip.verify_commands("python-project") == [["uv", "sync"], ["uv", "run", "pytest", "-q"]]
    assert ip.verify_commands("typescript-project") == [["npm", "install"], ["npm", "test"]]
    assert ip.verify_commands("unknown") == []


# --- Gap 3: GitHub remote ------------------------------------------------
def test_gh_create_cmd_private_by_default(tmp_path):
    cmd = ip.gh_create_cmd("my-proj", tmp_path)
    assert cmd[:4] == ["gh", "repo", "create", "my-proj"]
    assert "--private" in cmd and "--push" in cmd
    assert "--public" not in cmd


def test_gh_create_cmd_public_when_asked(tmp_path):
    assert "--public" in ip.gh_create_cmd("p", tmp_path, private=False)


# --- Gap 1: card links + projects MOC ------------------------------------
def test_memory_card_links_into_graph(profiles):
    cfg = ip.resolve(profiles, "cli", "product", ["none"], None)
    card = ip.memory_card("demo", cfg, [{"name": "test-writer"}])
    assert "## Links" in card
    assert "[[projects-moc]]" in card
    assert "[[windows-python-invocation]]" in card  # python stack decision


def test_append_to_moc_is_idempotent(tmp_path):
    moc = tmp_path / "projects-moc.md"
    assert ip.append_to_moc("alpha", "cli · python", moc=moc) is True
    assert ip.append_to_moc("alpha", "cli · python", moc=moc) is False  # already there
    assert ip.append_to_moc("beta", "web · typescript", moc=moc) is True
    text = moc.read_text(encoding="utf-8")
    assert text.count("[[alpha]]") == 1
    assert "[[beta]]" in text
    assert "type: moc" in text  # header written on first create


def test_all_build_types_resolve_and_compose(profiles):
    for build in profiles["build_types"]:
        stack = "react" if profiles["build_types"][build]["ask_stack"] else None
        cfg = ip.resolve(profiles, build, "product", ["api-keys"], stack)
        resolved, dropped = ip.classify_agents(cfg["agents"], profiles)
        assert dropped == [], f"build {build} maps to unknown agents: {dropped}"
        assert ip.compose_agents_md(f"demo-{build}", cfg)
