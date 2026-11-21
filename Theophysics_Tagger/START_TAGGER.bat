@echo off
cd /d "%~dp0tools"
start "" pythonw tagger3_gui.py
if errorlevel 1 python tagger3_gui.py
