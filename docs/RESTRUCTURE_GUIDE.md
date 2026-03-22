# Project Restructure Guide
## Autonomous AI News System — NA Project

> Run every command block in order. Do not skip steps. Open PowerShell in `D:\PROJECTS\NA` before starting.

---

## Step 1 — Create All Folders

```powershell
mkdir agents, pipeline, database, api, dashboard, config, logs, tests, scripts, docs
```

---

## Step 2 — Create `__init__.py` Files

```powershell
echo $null > agents\__init__.py
echo $null > pipeline\__init__.py
echo $null > database\__init__.py
echo $null > api\__init__.py
echo $null > dashboard\__init__.py
echo $null > config\__init__.py
echo $null > tests\__init__.py
```

---

## Step 3 — Move Agent Files

```powershell
Move-Item news_discovery_agent.py   agents\
Move-Item summarisation_agent.py    agents\
Move-Item duplicate_merger.py       agents\
Move-Item viral_score_engine.py     agents\
```

---

## Step 4 — Move Pipeline Files

```powershell
Move-Item intelligence_pipeline.py  pipeline\
Move-Item master_pipeline.py        pipeline\
```

---

## Step 5 — Move Database Files

```powershell
Move-Item db_schema.py              database\
Move-Item extend_schema.sql         database\
Move-Item seed_feeds.sql            database\
```

---

## Step 6 — Move API & Dashboard

```powershell
Move-Item api.py                    api\
Move-Item dashboard.py              dashboard\
```

---

## Step 7 — Move Test Files

```powershell
Move-Item test_pipeline.py          tests\
Move-Item verify_setup.py           tests\
```

---

## Step 8 — Move Scripts & Utilities

```powershell
Move-Item start_services.py         scripts\
Move-Item start_dashboard.bat       scripts\
Move-Item apply.py                  scripts\
Move-Item stop                      scripts\
```

> If any file in Step 8 does not exist, skip it — PowerShell will throw a warning but continue.

---

## Step 9 — Move Documentation

```powershell
Move-Item SETUP_SUMMARY.md          docs\
Move-Item POST_SETUP_CHANGES.md     docs\
Move-Item INTELLIGENCE_PIPELINE.md  docs\
Move-Item DEBUG_LOG.md              docs\
Move-Item TESTING_GUIDE.md          docs\
```

> Any .md files not listed above should also be moved to docs\

---

## Step 10 — Move the Word Document

```powershell
Move-Item AutonomousNews*.docx      docs\
```

---

## Step 11 — Update start_dashboard.bat

Overwrite the batch file with the corrected path:

```powershell
@"
@echo off
cd /d D:\PROJECTS\NA
call venv\Scripts\activate 2>nul
python scripts\start_services.py
"@ | Out-File -FilePath scripts\start_dashboard.bat -Encoding ascii
```

---

## Step 12 — Lock Package Versions

```powershell
pip freeze > requirements.txt
```

---

## Step 13 — Create .gitignore

```powershell
@"
# Environment
.env
venv/
.venv/

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# Logs
logs/
*.log

# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Images (generated at runtime)
images/
"@ | Out-File -FilePath .gitignore -Encoding utf8
```

---

## Step 14 — Fix Imports (Antigravity Prompt)

Open a fresh Antigravity conversation and paste this exactly:

```
I reorganized a Python project into this structure:
agents/ — news_discovery_agent.py, summarisation_agent.py, duplicate_merger.py, viral_score_engine.py
pipeline/ — intelligence_pipeline.py, master_pipeline.py
database/ — db_schema.py
api/ — api.py
dashboard/ — dashboard.py
tests/ — test_pipeline.py, verify_setup.py
scripts/ — start_services.py
Every folder has an __init__.py. The project root D:\PROJECTS\NA is the working directory.
Rewrite only the import block for each file so cross-package imports work correctly.
Use: from agents.news_discovery_agent import NewsDiscoveryAgent style absolute imports.
Show only the updated import section per file — not the full file. Python 3.13.
```

Apply the output imports to each file as instructed.

---

## Step 15 — Verify Final Structure

Run this to confirm everything is in place:

```powershell
tree /F /A
```

Expected output:

```
D:\PROJECTS\NA
|   .env
|   .gitignore
|   requirements.txt
|   README.md
|
+---agents
|       __init__.py
|       news_discovery_agent.py
|       summarisation_agent.py
|       duplicate_merger.py
|       viral_score_engine.py
|
+---pipeline
|       __init__.py
|       intelligence_pipeline.py
|       master_pipeline.py
|
+---database
|       __init__.py
|       db_schema.py
|       extend_schema.sql
|       seed_feeds.sql
|
+---api
|       __init__.py
|       api.py
|
+---dashboard
|       __init__.py
|       dashboard.py
|
+---config
|       __init__.py
|       brand_config.json     (created in Phase 5)
|
+---logs
|       pipeline.log
|
+---tests
|       __init__.py
|       test_pipeline.py
|       verify_setup.py
|
+---scripts
|       start_services.py
|       start_dashboard.bat
|       apply.py
|
+---docs
|       SETUP_SUMMARY.md
|       POST_SETUP_CHANGES.md
|       INTELLIGENCE_PIPELINE.md
|       DEBUG_LOG.md
|       TESTING_GUIDE.md
|       AutonomousNewsSystem_v2_MasterPlan.docx
```

---

## Step 16 — Smoke Test After Restructure

Run from the project root to confirm nothing is broken:

```powershell
# Test imports work from root
python -c "from agents.news_discovery_agent import NewsDiscoveryAgent; print('agents OK')"
python -c "from pipeline.intelligence_pipeline import IntelligencePipeline; print('pipeline OK')"
python -c "from agents.duplicate_merger import DuplicateMerger; print('merger OK')"
python -c "from agents.viral_score_engine import ViralScoreEngine; print('scorer OK')"
```

All four lines should print OK. If any fails, the import fix from Step 14 was not applied to that file.

---

## Step 17 — Run Full Test Suite

```powershell
python tests\test_pipeline.py
```

Expected: **10/10 tests passed** — same as before the restructure.

---

## Done

Your project is now professionally organized. Next step: **Phase 5 — Branding Layer**.  
Come back with your test results and the Phase 5 prompts will be waiting.
