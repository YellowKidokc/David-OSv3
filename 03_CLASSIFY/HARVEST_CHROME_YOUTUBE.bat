@echo off
rem Harvest Chrome YouTube watch history into the prediction ledger. Code: 02_CLASSIFICATION\harness.
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp002_CLASSIFICATION"
"%PY%" -m harness.adapters.chrome_history
pause
