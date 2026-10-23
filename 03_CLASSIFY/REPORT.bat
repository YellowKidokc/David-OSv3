@echo off
rem 03_CLASSIFY - rebuild 01_SIDECARS\docs\SIDECAR_CLASSIFICATIONS.md + .html from the live cards, then open the page.
rem Card reader (harness.adapters.sidecars) is vendored in 02_CLASSIFICATION.
cd /d "%~dp0"
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" 01_SIDECARS\sidecar_report.py %*
if errorlevel 1 (pause & exit /b)
start "" "01_SIDECARS\docs\SIDECAR_CLASSIFICATIONS.html"
