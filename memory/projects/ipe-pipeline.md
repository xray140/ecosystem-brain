---
type: project
status: active
created: 2026-06-29
host: Verdun10
stack: [python]
tags: [project, python, iso50001, energie]
---
# ipe-pipeline

Renommé depuis `sensor-csv-pipeline` le 2026-07-20 (paquet `ipe_pipeline`,
branche `main`, dossier renommé le 2026-09-03) — le projet n'est pas un pipeline CSV générique mais
l'outil de suivi des IPE ISO 50001 de l'usine LSF Verdun.

## Stack
Data pipeline Python (uv, pandas, statsmodels, openpyxl) + générateur Power
Query M. Livrable principal : `data/IPE_LIVE.xlsx`, classeur auto-actualisable
(24 requêtes M injectées par COM) qui reconstruit conso/IPE des 5 UES depuis
les compteurs SCADA et les compare aux TDB officiels.

## Agents installed
data-engineer, python-pro, test-writer, security-auditor

## Paths
- Project: `C:\Users\Verdun-10\ipe-pipeline` (renommage dossier achevé le 2026-09-03 ; le verrou de 2026-07-20 était Excel tenant `data/IPE_LIVE.xlsx`)
- Repo: `https://github.com/xray140/ipe-pipeline` (privé, créé le 2026-09-03, branche `main`)

## Links
- [[projects-moc]]
- [[windows-python-invocation]]
- [[powershell-utf8-bom]]
