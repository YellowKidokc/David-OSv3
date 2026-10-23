@echo off
cd /d "%~dp0.."
python gui\fis_search_workbench.py
if errorlevel 1 pause
