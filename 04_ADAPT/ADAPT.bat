@echo off
rem 04_ADAPT - legacy cards -> mim.v1 stamp. Drag a folder onto this file, or run it and pick one.
cd /d "%~dp0"
python adapt_cards.py %*
pause
