@echo off
rem One-time setup for the 03_CLASSIFY prediction harness: venv + engine deps + smoke test.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-prediction.txt
.venv\Scripts\python.exe 02_CLASSIFICATION\tests\smoke.py
pause
