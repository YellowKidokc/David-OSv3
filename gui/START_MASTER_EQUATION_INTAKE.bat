@echo off
cd /d "%~dp0.."
python gui\master_equation_intake_gui.py
if errorlevel 1 pause
