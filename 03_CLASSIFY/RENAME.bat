@echo off
rem 03_CLASSIFY - open the Renamer review window (03_RENAMING). Drag a folder onto this file, or it opens S:\PROCESSED.
rem Rules (context clue words): 03_RENAMING\rename_rules.yaml. Nothing renames until you press Apply.
cd /d "%~dp0"
if "%~1"=="" (
  python 03_RENAMING\renamer_gui.py "S:\PROCESSED"
) else (
  python 03_RENAMING\renamer_gui.py "%~1"
)
if errorlevel 1 pause
