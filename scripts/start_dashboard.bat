@echo off
cd /d D:\PROJECTS\NA
call venv\Scripts\activate 2>nul
python scripts\start_services.py
