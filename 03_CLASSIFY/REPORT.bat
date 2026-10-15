@echo off
rem 03_CLASSIFY - rebuild 01_SIDECARS\docs\SIDECAR_CLASSIFICATIONS.md + .html from the live cards, then open the page.
rem Needs Prediction_GUI for the card reader.
if "%PREDICTION_GUI%"=="" set "PREDICTION_GUI=D:\GitHub\Prediction_GUI"
cd /d "%~dp0"
python 01_SIDECARS\sidecar_report.py %*
if errorlevel 1 (pause & exit /b)
start "" "01_SIDECARS\docs\SIDECAR_CLASSIFICATIONS.html"
