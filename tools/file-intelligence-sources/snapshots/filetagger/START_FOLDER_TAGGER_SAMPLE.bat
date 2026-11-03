@echo off
cd /d "%~dp0"
python foldertagger.py "%~dp0sample" --force
pause
