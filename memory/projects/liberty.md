---
type: project
status: active
created: 2026-08-24
host: Verdun10
stack: [python]
tags: [project, python, betting, quant, research]
---
# liberty

Quantitative sports betting research platform — football and tennis. Scaffolded
2026-08-24, briefly marked cancelled the same day, then **revived the same day**
with a full research brief. The earlier "torn down" note was wrong: the scaffold
and the private GitHub repo (`xray140/liberty`) both survived.

**Three-year horizon of pure research and paper trading before any real money.**

## The constraint that defines the project

Run from France, and that redefines what success can mean:

- ANJ caps **TRJ at 85 %** → French books run ~11–15 % margin vs Pinnacle's 2–3 %.
- **Betting exchanges are unlicensed in France.** Betfair Exchange withdrew after
  the 2010 law. No lay side, no depth, no low-margin venue.
- **Pinnacle closed public API access 2025-07-23** and is not ANJ-licensed.

So CLV has two meanings, and the schema encodes both: `bet.clv_log_ref` (sharp
benchmark, not bettable from FR) and `bet.clv_log_venue` (tradeable, heavily
vigged). A strategy must clear both gates. Empirically confirmed on ATP 2024:
Pinnacle overround 2.61 %, Bet365 5.17 %.

Decisions taken on the owner's behalf when he said "as you think its better":
research-only posture, **€0 data spend for now**, **tennis before football**,
poller built but parked pending a free API key.

## Other landscape facts worth not rediscovering

- **FBref lost all Opta advanced stats on 2026-01-20** (Stats Perform terminated
  the Sports Reference agreement). Free league-scale football xG effectively no
  longer exists; Understat is the last one standing and revises its xG
  retroactively, which is leakage unless snapshotted.
- tennis-data.co.uk **robots.txt disallows /2000/–/2005/**, so ATP coverage
  legitimately starts 2006, WTA 2007.
- Disk: single C: drive, ~259 GB free → **Betfair PRO football (TB-scale) is
  ruled out on this machine.**

## Stack
Python 3.12+ / uv, DuckDB + Parquet, Polars, httpx + protego, Typer.
`mypy --strict`, ruff, pytest + hypothesis. Never row-at-a-time DuckDB inserts —
see `liberty.ingest.bulk`.

## Agents installed
data-engineer, python-pro, test-writer, security-auditor

## Paths
- Project: `C:\Users\Verdun-10\liberty`
- Repo: `https://github.com/xray140/liberty` (private)
- Phase 0 design doc: delivered in-session 2026-08-24

## Links
- [[projects-moc]]
- [[windows-python-invocation]]
- [[powershell-utf8-bom]]
