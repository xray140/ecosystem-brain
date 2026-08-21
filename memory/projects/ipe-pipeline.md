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
branche `ipe-pipeline`) — le projet n'est pas un pipeline CSV générique mais
l'outil de suivi des IPE ISO 50001 de l'usine LSF Verdun.

## Stack
Data pipeline Python (uv, pandas, statsmodels, openpyxl) + générateur Power
Query M. Livrable principal : `data/IPE_LIVE.xlsx`, classeur auto-actualisable
(24 requêtes M injectées par COM) qui reconstruit conso/IPE des 5 UES depuis
les compteurs SCADA et les compare aux TDB officiels.

## Agents installed
data-engineer, python-pro, test-writer, security-auditor

## Paths
- Project: `C:\Users\Verdun-10\sensor-csv-pipeline` (renommage dossier -> `ipe-pipeline` en attente : verrou processus 2026-07-20 ; repo/paquet déjà renommés)

## Links
- [[projects-moc]]
- [[windows-python-invocation]]
- [[powershell-utf8-bom]]
