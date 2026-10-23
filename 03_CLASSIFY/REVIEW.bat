@echo off
rem 03_CLASSIFY - open the review window (02_CLASSIFICATION). Engines and venv are local now.
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp0"
"%PY%" 02_CLASSIFICATION\gui\review.py %*
if errorlevel 1 pause
