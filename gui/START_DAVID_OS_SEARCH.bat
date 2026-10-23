@echo off
cd /d "%~dp0.."
python scripts\start_search_site.py
if errorlevel 1 pause
