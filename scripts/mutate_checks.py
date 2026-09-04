"""Break each of this repo's checks and confirm its tests go red.

The rule in decisions/verification-integrity says a check that cannot fail is
decoration. That applies to the tests written FOR those checks too — a green
suite proves nothing unless it would go red for the defect it claims to guard.

Each mutation is a one-line textual change to the SOURCE, chosen to reintroduce
the exact defect the tool exists for. The file is restored either way, including
on failure — and the restore is VERIFIED by reading the file back, because a
write can fail too. On 2026-09-04 one did: a concurrent reader made it fail with
EINVAL, the exception escaped the `finally`, and a live `elif False:` was left
in scripts/selfcheck.py. The old wording described the `finally`, which handles
a failing test, not a failing restore. A harness that can silently leave a
mutation behind is worse than no harness, because everything downstream then
measures poisoned source.

Its first run found a real hole: the truncation test subclassed the embedder
and re-implemented the truncation inside the test, so it passed no matter what
the source did. Nine of ten mutations were caught; that one was not.

Not wired into CI — it rewrites source files, and a killed run would leave a
mutation behind. Run it deliberately, after adding or changing a check:

    uv run --no-project python scripts/mutate_checks.py
"""

import pathlib
import subprocess
import sys
import time

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
        # Was "stop noticing the offline fallback", anchored on `args.offline`.
        # That flag went with Ollama in v4.8.0, so the mutation stopped applying
        # and the harness has exited 1 on a skip ever since — a mutant that
        # cannot be planted proves nothing about the test that should catch it.
        # The property it guarded survives the backend: a status check that
        # cannot report a degraded index.
        "memory-search: report an under-covered index as healthy",
        "skills/memory/memory-search.py",
        "        if missing > 0:",
        "        if False:",
        "tests/test_memory_search.py",
    ),
    (
        # Anchored on the Ollama request body until v4.8.0. MAX_EMBED_CHARS
        # outlived the backend that forced it — the head of a note carries its
        # topic — so the cap moved into HashEmbedder and the mutation follows it.
        "memory-search: drop the truncation, so a long note drowns its own topic",
        "skills/memory/memory-search.py",
        "        for tok in WORD_RE.findall(text[:MAX_EMBED_CHARS].lower()):",
        "        for tok in WORD_RE.findall(text.lower()):",
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
    (
        "maintenance: capture the children in the locale encoding again",
        "scripts/maintenance.py",
        '        encoding="utf-8",\n        errors="replace",\n',
        "",
        "tests/test_maintenance.py",
    ),
    (
        "selfcheck: let a deleted roadmap claim pass as nothing to check",
        "scripts/selfcheck.py",
        '            fail(f"roadmap: the \'{label}\' claim is gone — nothing left to check")',
        "            pass",
        "tests/test_selfcheck_checks.py",
    ),
    (
        "selfcheck: stop comparing the roadmap claim to the repo",
        "scripts/selfcheck.py",
        "        elif m.group(1) != actual:",
        "        elif False:",
        "tests/test_selfcheck_checks.py",
    ),
    (
        "template: let a dependency float again",
        "templates/typescript-project/package.json",
        '"typescript": "5.9.3"',
        '"typescript": "^5.9.3"',
        "tests/test_selfcheck.py",
    ),
    (
        "init_project: hand back the named override file, not the launchable one",
        "scripts/init_project.py",
        "        found = shutil.which(name, path=str(parent))",
        "        found = str(Path(value)) if Path(value).is_file() else None",
        "tests/test_init_project.py",
    ),
    (
        "verify_templates: stop following the log npm points at",
        "scripts/verify_templates.py",
        "            deeper = follow_debug_log(output)",
        '            deeper = ""',
        "tests/test_verify_templates.py",
    ),
    (
        "verify_templates: stop printing the runtime on a green run",
        "scripts/verify_templates.py",
        '                print(f"  [--] {template:22s} runtime: {runtime_versions(tool)}")',
        "                pass",
        "tests/test_verify_templates.py",
    ),
    (
        # This anchor tracks the pin on purpose. Bumping node without revisiting
        # the mutant makes the harness skip it and exit 1, which is the intended
        # nag: the pin and the test that guards it move together.
        "ci: pin node by major, so npm keeps drifting",
        ".github/workflows/ci.yml",
        "node-version: 24.20.0",
        "node-version: 24",
        "tests/test_selfcheck.py",
    ),
    (
        # The rules table is 20 regexes and one gate; line coverage proves only
        # that the loop ran. These three ask the harder question.
        "scan_agent: apply only the first rule in the table",
        "scripts/scan_agent.py",
        "    for severity, label, pattern, why in RULES:",
        "    for severity, label, pattern, why in RULES[:1]:",
        "tests/test_scan_agent_rules.py",
    ),
    (
        "scan_agent: neuter one rule's regex, leaving its label in place",
        "scripts/scan_agent.py",
        r'        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),',
        r'        re.compile(r"^(?!x)x_never_matches", re.I),',
        "tests/test_scan_agent_rules.py",
    ),
    (
        "scan_agent: stop running the tool-grant check (the one detection that is code)",
        "scripts/scan_agent.py",
        "    findings.extend(_check_tool_grants(content))",
        "    pass",
        "tests/test_scan_agent_rules.py",
    ),
    (
        "selfcheck: let a network phrase in a RED run mean 'never ran' again",
        'scripts/selfcheck.py',
        '        if _toolchain_unreachable(out, PYTEST_RAN):',
        '        if _toolchain_unreachable(out):',
        'tests/test_selfcheck_checks.py',
    ),
    (
        'doctor: stop reading the registry back against the repo',
        'scripts/doctor.py',
        '            if not (directory / pattern.format(name=name)).exists():',
        '            if False:',
        'tests/test_doctor.py',
    ),
    (
        'update-agents: certify a github entry whose file is gone',
        'scripts/update-agents.py',
        '    if not repo_file.exists():\n        return "missing-in-repo"\n\n    repo, path = parsed',
        '    repo, path = parsed',
        'tests/test_update_agents.py',
    ),
    (
        'guard_destructive: the hook decides allow instead of block',
        'hooks/scripts/guard_destructive.py',
        '        print(json.dumps({"decision": "block", "reason": reason}))\n        return 2',
        '        print(json.dumps({"decision": "allow", "reason": reason}))\n        return 0',
        'tests/test_guard_destructive.py',
    ),
    (
        'guard_destructive: read a payload key that is never sent, so nothing is inspected',
        'hooks/scripts/guard_destructive.py',
        '    command = (payload.get("tool_input") or {}).get("command") or ""',
        '    command = (payload.get("toolInput") or {}).get("command") or ""',
        'tests/test_guard_destructive.py',
    ),
    (
        "ci: pin an action to a mutable tag",
        ".github/workflows/ci.yml",
        "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
        "actions/setup-node@v7",
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

def restore(path: pathlib.Path, original: str, attempts: int = 5) -> bool:
    """Put the file back and prove it. True only when the bytes match again.

    Retried: on Windows a concurrent reader can make the write fail with EINVAL,
    which is transient. Verified: a write that reports success but leaves the
    file changed is the failure mode this whole harness exists to catch, and it
    would be absurd to be blind to it here.
    """
    for attempt in range(attempts):
        try:
            path.write_text(original, encoding="utf-8", newline="\n")
        except OSError:
            time.sleep(0.2 * (attempt + 1))
            continue
        try:
            if path.read_text(encoding="utf-8") == original:
                return True
        except OSError:
            pass
        time.sleep(0.2 * (attempt + 1))
    return False


def run(mutations=MUTATIONS) -> int:
    caught = missed = skipped = 0
    stranded: list[str] = []
    for label, src, find, repl, tests in mutations:
        p = pathlib.Path(src)
        original = p.read_text(encoding="utf-8")
        if original.count(find) != 1:
            print(f"  [skip] {label}\n         anchor matched {original.count(find)}x")
            skipped += 1
            continue
        p.write_text(original.replace(find, repl), encoding="utf-8", newline="\n")
        try:
            r = subprocess.run(
                [*PYTEST, tests],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        finally:
            if not restore(p, original):
                stranded.append(src)
                print(f"  [!!] {label}")
                print(f"       {src} IS STILL MUTATED — restore it before doing anything else:")
                print(f"       git checkout -- {p.as_posix()}")
        if r.returncode != 0:
            caught += 1
            print(f"  [caught] {label}")
        else:
            missed += 1
            print(f"  [MISSED] {label}\n           {tests} still passed with the defect reintroduced")

    print(f"\ncaught {caught}, missed {missed}, skipped {skipped} of {len(mutations)}")
    if stranded:
        print(f"\n[!!] {len(stranded)} file(s) left mutated: {', '.join(sorted(set(stranded)))}")
        print("     Every check that runs before you fix this is measuring poisoned source.")
    return 1 if missed or skipped or stranded else 0


if __name__ == "__main__":
    sys.exit(run())
