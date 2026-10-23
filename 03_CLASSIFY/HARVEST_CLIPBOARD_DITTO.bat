@echo off
rem Harvest Ditto clipboard history into the prediction ledger.
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp002_CLASSIFICATION"
"%PY%" -m harness.adapters.clipboard ditto %*
pause
