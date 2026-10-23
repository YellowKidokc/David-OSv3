@echo off
rem Register a dropped engine folder (writes engine.json, registers in ledger). Code: 02_CLASSIFICATION\intake.
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp002_CLASSIFICATION"
if "%~1"=="" (
  echo Drag an engine folder onto this file, or run:  INTAKE.bat engines\my_engine
  pause
  exit /b
)
"%PY%" intake\intake.py "%~1"
pause
