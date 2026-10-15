@echo off
rem 03_CLASSIFY - open the review window (02_CLASSIFICATION). Engines come from Prediction_GUI; its venv runs this.
if "%PREDICTION_GUI%"=="" set "PREDICTION_GUI=D:\GitHub\Prediction_GUI"
set PY=python
if exist "%PREDICTION_GUI%\.venv\Scripts\python.exe" set "PY=%PREDICTION_GUI%\.venv\Scripts\python.exe"
cd /d "%~dp0"
"%PY%" 02_CLASSIFICATION\gui\review.py %*
if errorlevel 1 pause
