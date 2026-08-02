"""Break each of this repo's checks and confirm its tests go red.

The rule in decisions/verification-integrity says a check that cannot fail is
decoration. That applies to the tests written FOR those checks too — a green
suite proves nothing unless it would go red for the defect it claims to guard.

Each mutation is a one-line textual change to the SOURCE, chosen to reintroduce
the exact defect the tool exists for. The file is restored either way, including
on failure.

Its first run found a real hole: the truncation test subclassed OllamaEmbedder
and re-implemented the truncation inside the test, so it passed no matter what
the source did. Nine of ten mutations were caught; that one was not.

Not wired into CI — it rewrites source files, and a killed run would leave a
mutation behind. Run it deliberately, after adding or changing a check:

    uv run --no-project python scripts/mutate_checks.py
"""

import pathlib
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# (label, source file, find, replace, test file)
MUTATIONS = [
    (
        "project_doctor: 'elsewhere' collapses back into 'gone'",
        "scripts/project_doctor.py",
        "    return bool(anchor) and not Path(anchor).exists()",
        "    return False",
        "tests/test_project_doctor.py",
    ),
    (
        "task_doctor: judge on State instead of last result",
        "scripts/task_doctor.py",
        "    if result not in OK_RESULTS:",
        "    if False:",
        "tests/test_task_doctor.py",
    ),
    (
        "task_doctor: stop caring how old the last success is",
        "scripts/task_doctor.py",
        "    if age > STALE_AFTER:",
        "    if False:",
        "tests/test_task_doctor.py",
    ),
    (
        "agent_usage: let first-party agents become removal candidates",
        "scripts/agent_usage.py",
        '        if row["local"]:',
        "        if False:",
        "tests/test_agent_usage.py",
    ),
    (
        "memory-search: stop noticing the offline fallback",
        "skills/memory/memory-search.py",
        "        if offline and not args.offline:",
        "        if False:",
        "tests/test_memory_search.py",
    ),
    (
        "memory-search: drop the truncation that fixed the 500",
        "skills/memory/memory-search.py",
        '            {"model": self.model, "prompt": text[:MAX_EMBED_CHARS]}',
        '            {"model": self.model, "prompt": text}',
        "tests/test_memory_search.py",
    ),
    (
        "rollback: skip the scan on the way back",
        "scripts/update-agents.py",
        '    if worst(scan(content)) == "HIGH":',
        "    if False:",
        "tests/test_rollback.py",
    ),
    (
        "layout: accept a traversing name",
        "scripts/layout.py",
        '    if not SAFE_NAME.fullmatch(name) or ".." in name:',
        "    if False:",
        "tests/test_install_agent.py",
    ),
    (
        "verify_templates: ignore a red baseline",
        "scripts/verify_templates.py",
        "        if c.returncode != 0:",
        "        if False:",
        "tests/test_verify_templates.py",
    ),
    (
        "selfcheck: stop flagging the cp-into-.claude instruction",
        "scripts/selfcheck.py",
        "                if RAW_COPY.search(line):",
        "                if False:",
        "tests/test_selfcheck_checks.py",
    ),
    # --- gates that predate this session -----------------------------------
    # Never mutation-tested before. These are the oldest and the most
    # security-critical, which is the worst combination to leave unverified.
    (
        "scan_agent: nothing ever scores HIGH again",
        "scripts/scan_agent.py",
        '        (f["severity"] for f in findings), key=lambda s: SEVERITY[s], default="CLEAN"',
        '        ("CLEAN" for f in findings), key=lambda s: 0, default="CLEAN"',
        "tests/test_scan_agent.py",
    ),
    (
        "install-agent: let HIGH-risk content install anyway",
        "scripts/install-agent.py",
        '    if level == "HIGH" and not args.force:',
        "    if False:",
        "tests/test_install_agent_main.py",
    ),
    (
        "update-agents: stop quarantining a poisoned upstream",
        "scripts/update-agents.py",
        '    if worst(scan(new_content)) == "HIGH":',
        "    if False:",
        "tests/test_update_agents.py",
    ),
    (
        "doctor: stop noticing an edited live copy",
        "scripts/doctor.py",
        '        elif live.read_text(encoding="utf-8") != expected:',
        "        elif False:",
        "tests/test_doctor.py",
    ),
    (
        "bootstrap: stop expanding the {{ECOSYSTEM_ROOT}} token",
        "scripts/bootstrap.py",
        "        text.replace(TOKEN, bash_root)",
        "        text",
        "tests/test_selfcheck_paths.py",
    ),
    (
        "guard_destructive: stop requiring -r, so nothing is catastrophic",
        "hooks/scripts/guard_destructive.py",
        '    if "r" not in flags:  # non-recursive rm cannot wipe a tree',
        "    if True:",
        "tests/test_guard_destructive.py",
    ),
    (
        "selfcheck: accept any model in agent frontmatter",
        "scripts/selfcheck.py",
        '    if m and m.group(1) not in KNOWN_MODELS and not m.group(1).startswith("claude-"):',
        "    if False:",
        "tests/test_selfcheck.py",
    ),
]

PYTEST = [
    "uv",
    "run",
    "--with-requirements",
    "requirements-dev.txt",
    "--no-project",
    "pytest",
    "-q",
    "--no-header",
    "-x",
]

caught = missed = skipped = 0
for label, src, find, repl, tests in MUTATIONS:
    p = pathlib.Path(src)
    original = p.read_text(encoding="utf-8")
    if original.count(find) != 1:
        print(f"  [skip] {label}\n         anchor matched {original.count(find)}x")
        skipped += 1
        continue
    p.write_text(original.replace(find, repl), encoding="utf-8", newline="\n")
    try:
        r = subprocess.run([*PYTEST, tests], capture_output=True, text=True, check=False)
    finally:
        p.write_text(original, encoding="utf-8", newline="\n")
    if r.returncode != 0:
        caught += 1
        print(f"  [caught] {label}")
    else:
        missed += 1
        print(f"  [MISSED] {label}\n           {tests} still passed with the defect reintroduced")

print(f"\ncaught {caught}, missed {missed}, skipped {skipped} of {len(MUTATIONS)}")
sys.exit(1 if missed or skipped else 0)
