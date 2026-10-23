@echo off
rem Prediction harness GUI (engine scoreboard). Code lives in 02_CLASSIFICATION; venv at 03_CLASSIFY\.venv.
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp002_CLASSIFICATION"
"%PY%" gui\app.py
pause
