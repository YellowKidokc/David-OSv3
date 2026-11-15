@echo off
setlocal
cd /d "%~dp0"
py -3 filetagger_gui.py
if errorlevel 1 (
  python filetagger_gui.py
)
endlocal

