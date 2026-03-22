# Restructure script executing Steps 1 to 13
mkdir agents, pipeline, database, api, dashboard, config, logs, tests, scripts, docs -Force
echo $null > agents\__init__.py
echo $null > pipeline\__init__.py
echo $null > database\__init__.py
echo $null > api\__init__.py
echo $null > dashboard\__init__.py
echo $null > config\__init__.py
echo $null > tests\__init__.py

Move-Item -Force news_discovery_agent.py agents\ -ErrorAction SilentlyContinue
Move-Item -Force summarisation_agent.py agents\ -ErrorAction SilentlyContinue
Move-Item -Force duplicate_merger.py agents\ -ErrorAction SilentlyContinue
Move-Item -Force viral_score_engine.py agents\ -ErrorAction SilentlyContinue

Move-Item -Force intelligence_pipeline.py pipeline\ -ErrorAction SilentlyContinue
Move-Item -Force master_pipeline.py pipeline\ -ErrorAction SilentlyContinue

Move-Item -Force db_schema.py database\ -ErrorAction SilentlyContinue
Move-Item -Force extend_schema.sql database\ -ErrorAction SilentlyContinue
Move-Item -Force seed_feeds.sql database\ -ErrorAction SilentlyContinue
Move-Item -Force add_summaries_table.sql database\ -ErrorAction SilentlyContinue

Move-Item -Force api.py api\ -ErrorAction SilentlyContinue
Move-Item -Force dashboard.py dashboard\ -ErrorAction SilentlyContinue

Move-Item -Force test_pipeline.py tests\ -ErrorAction SilentlyContinue
Move-Item -Force verify_setup.py tests\ -ErrorAction SilentlyContinue

Move-Item -Force start_services.py scripts\ -ErrorAction SilentlyContinue
Move-Item -Force start_dashboard.bat scripts\ -ErrorAction SilentlyContinue
Move-Item -Force apply.py scripts\ -ErrorAction SilentlyContinue
Move-Item -Force stop scripts\ -ErrorAction SilentlyContinue

Move-Item -Force SETUP_SUMMARY.md docs\ -ErrorAction SilentlyContinue
Move-Item -Force POST_SETUP_CHANGES.md docs\ -ErrorAction SilentlyContinue
Move-Item -Force INTELLIGENCE_PIPELINE.md docs\ -ErrorAction SilentlyContinue
Move-Item -Force DEBUG_LOG.md docs\ -ErrorAction SilentlyContinue
Move-Item -Force TESTING_GUIDE.md docs\ -ErrorAction SilentlyContinue
Move-Item -Force RESTRUCTURE_GUIDE.md docs\ -ErrorAction SilentlyContinue
Move-Item -Force AutonomousNews*.docx docs\ -ErrorAction SilentlyContinue

@"
@echo off
cd /d D:\PROJECTS\NA
call venv\Scripts\activate 2>nul
python scripts\start_services.py
"@ | Out-File -FilePath scripts\start_dashboard.bat -Encoding ascii

pip freeze > requirements.txt

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
