---
description: Which installed agents actually get invoked — and which never have.
---
Every installed agent costs SessionStart context, because the suggester lists it.
Nothing measured whether any were ever used, so the roster only ever grew.

Claude Code records each delegation in its session transcripts, so the question
is answerable from data already on disk. Run:

```
uv run --no-project python {{ECOSYSTEM_ROOT}}/scripts/agent_usage.py
```

`--unused` prints just the candidate names, one per line, for piping.

## Report the number, not a verdict

Transcripts are **local** and can be rotated or deleted. "Never invoked" means
"not in the transcripts on this machine" — an agent used daily on another PC
reads as unused here. Say that when presenting the result; never remove an agent
on this evidence alone.

First-party agents are listed separately and are never removal candidates. They
are the squad the SessionStart hook advertises on purpose: a zero there means
*start delegating to it*, not *delete it*. If several first-party agents show
zero, that is worth mentioning as a habit to change, not a cleanup to run.

## Removing one, once the user decides

```
rm agents/<name>.md ~/.claude/agents/<name>.md
```

then drop its entry from `registry/installed.json` and re-run
`{{ECOSYSTEM_ROOT}}/scripts/doctor.py` to confirm nothing drifted.
