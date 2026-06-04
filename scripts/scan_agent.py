#!/usr/bin/env python3
"""Scan an agent/skill/command markdown file for malicious or risky content.

Threat model: you are pulling untrusted markdown from public GitHub repos and
activating it as a Claude Code agent/command. A hostile file could try to:
  - inject instructions ("ignore previous instructions", "you are now ...")
  - exfiltrate secrets (read .env / ~/.ssh then curl them to a webhook)
  - run dangerous shell (curl | bash, rm -rf, chmod 777, base64 -d | sh)
  - hide instructions (zero-width chars, HTML comments, long base64 blobs)
  - over-grant tools (unrestricted Bash on a "read-only" agent)

Usage:
    uv run python scripts/scan_agent.py path/to/file.md
    # exit 0 = clean/low, 1 = medium warnings, 2 = high (should block)

Importable: `from scan_agent import scan; findings = scan(content)`
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# (severity, label, compiled pattern, explanation)
RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    # --- prompt injection -------------------------------------------------
    (
        "HIGH",
        "prompt-injection",
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
        "attempts to override the system/parent instructions",
    ),
    (
        "HIGH",
        "prompt-injection",
        re.compile(
            r"disregard\s+(your|the|all)\s+(system\s+prompt|previous|instructions)",
            re.I,
        ),
        "attempts to discard the existing instructions",
    ),
    (
        "MEDIUM",
        "role-override",
        re.compile(
            r"you\s+are\s+now\s+(a\s+)?(different|new|unrestricted|dan\b)", re.I
        ),
        "attempts to redefine the assistant's role",
    ),
    (
        "MEDIUM",
        "instruction-injection",
        re.compile(r"\bnew\s+(system\s+)?instructions?\s*:", re.I),
        "injects a new instruction block",
    ),
    # --- secret exfiltration ---------------------------------------------
    (
        "HIGH",
        "secret-read",
        re.compile(
            r"(cat|type|read|print|echo)\s+[^\n]*\.(env|identity\.local\.env)\b", re.I
        ),
        "reads secret/.env files",
    ),
    (
        "HIGH",
        "ssh-key-read",
        re.compile(r"(cat|read|copy)\s+[^\n]*\.ssh[/\\](id_|known_hosts|config)", re.I),
        "reads SSH private keys or config",
    ),
    (
        "HIGH",
        "credential-grep",
        re.compile(
            r"(grep|rg|findstr)[^\n]*(password|secret|api[_-]?key|token|aws_)", re.I
        ),
        "greps for credentials across files",
    ),
    # --- dangerous shell --------------------------------------------------
    (
        "HIGH",
        "curl-pipe-shell",
        re.compile(r"(curl|wget)\s+[^\n|]*\|\s*(bash|sh|zsh|python)", re.I),
        "pipes a remote download straight into a shell",
    ),
    (
        "HIGH",
        "obfuscated-exec",
        re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(bash|sh|python)", re.I),
        "decodes base64 and executes it",
    ),
    (
        "HIGH",
        "recursive-delete",
        re.compile(r"\brm\s+-[rf]{1,2}\s+(/|~|\$HOME|\*)", re.I),
        "recursive delete of root/home/wildcard",
    ),
    (
        "MEDIUM",
        "world-writable",
        re.compile(r"\bchmod\s+(-R\s+)?0?777\b", re.I),
        "sets world-writable permissions",
    ),
    (
        "MEDIUM",
        "tls-disabled",
        re.compile(
            r"(curl\s+[^\n]*\s-k\b|--no-check-certificate|verify\s*=\s*False)", re.I
        ),
        "disables TLS certificate verification",
    ),
    # --- exfiltration endpoints ------------------------------------------
    (
        "MEDIUM",
        "exfil-endpoint",
        re.compile(
            r"(curl|wget|fetch|requests\.post)\s+[^\n]*https?://[^\s\"')]+", re.I
        ),
        "sends data to an external endpoint (review the URL)",
    ),
    # --- hidden content ---------------------------------------------------
    (
        "HIGH",
        "zero-width-chars",
        re.compile(r"[​‌‍⁠﻿]"),
        "contains zero-width / invisible characters (hidden text)",
    ),
    (
        "MEDIUM",
        "html-comment",
        re.compile(r"<!--.*?(instruction|ignore|system|prompt).*?-->", re.I | re.S),
        "hides directive text inside an HTML comment",
    ),
    (
        "LOW",
        "long-base64",
        re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"),
        "very long base64 blob (possible hidden payload)",
    ),
]

FENCE_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def scan(content: str) -> list[dict]:
    """Return a list of findings: {severity, label, why, snippet}."""
    findings: list[dict] = []
    for severity, label, pattern, why in RULES:
        for m in pattern.finditer(content):
            snippet = m.group(0)[:80].replace("\n", " ")
            findings.append(
                {"severity": severity, "label": label, "why": why, "snippet": snippet}
            )
    findings.extend(_check_tool_grants(content))
    return findings


def _check_tool_grants(content: str) -> list[dict]:
    """Flag a read-only-sounding agent that grants unrestricted Bash/Write."""
    out: list[dict] = []
    m = FENCE_RE.match(content)
    if not m:
        return out
    fm = m.group(1).lower()
    desc_readonly = any(
        w in fm for w in ("read-only", "read only", "audit", "review", "scan")
    )
    grants_write = bool(re.search(r"\b(bash|write|edit)\b", fm))
    if desc_readonly and grants_write:
        out.append(
            {
                "severity": "MEDIUM",
                "label": "tool-mismatch",
                "why": "describes itself as read-only/audit but grants write/exec tools",
                "snippet": "frontmatter tools vs description",
            }
        )
    return out


def worst(findings: list[dict]) -> str:
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    return max(
        (f["severity"] for f in findings), key=lambda s: order[s], default="CLEAN"
    )


def format_report(findings: list[dict]) -> str:
    if not findings:
        return "  [clean] no risky patterns found"
    lines = []
    for f in sorted(findings, key=lambda x: x["severity"]):
        lines.append(f"  [{f['severity']:6s}] {f['label']:20s} {f['why']}")
        lines.append(f"           ↳ {f['snippet']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", type=Path)
    args = ap.parse_args(argv)
    content = args.file.read_text(encoding="utf-8", errors="replace")
    findings = scan(content)
    print(f"scan: {args.file.name}")
    print(format_report(findings))
    level = worst(findings)
    print(f"\nverdict: {level}")
    return {"CLEAN": 0, "LOW": 0, "MEDIUM": 1, "HIGH": 2}[level]


if __name__ == "__main__":
    raise SystemExit(main())
