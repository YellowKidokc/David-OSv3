@echo off
setlocal
cd /d "%~dp0"
python BATCH_ALL.py %*
pause
