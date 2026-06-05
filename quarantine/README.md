# quarantine/

Holding pen for agent/skill/command content the security scanner (`scan_agent.py`)
refused to activate — a HIGH-risk install (`install-agent.py`) or a HIGH-risk
upstream update (`update-agents.py`).

**Nothing here is active.** Files land here so you can review *what* was flagged
before deciding to trust, edit, or discard them.

## Workflow when something lands here
1. Read the file — the first lines state why it was quarantined.
2. Scan it explicitly: `uv run python scripts/scan_agent.py quarantine/<name>.md`
3. Decide:
   - **Trust it** → `uv run python scripts/install-agent.py --file quarantine/<name>.md --force`
   - **Discard** → delete the file.

The quarantined `.md` files are **gitignored** (we don't commit untrusted
content). Only this README is tracked.
