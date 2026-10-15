@echo off
rem 01_PROFILE - the doorway wizard. Drag a folder onto this file, or run it and pick one.
cd /d "%~dp0"
python profile_wizard.py %*
if errorlevel 1 pause
