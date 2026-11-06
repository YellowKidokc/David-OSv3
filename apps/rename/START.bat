@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist "..\..\.venv\Scripts\python.exe" set "PY=..\..\.venv\Scripts\python.exe"
echo Rename app  (PROPOSALS ONLY: nothing is renamed)
set /p FOLDER=Folder to propose names for: 
if "%FOLDER%"=="" goto :eof
"%PY%" src\run.py "%FOLDER%"
echo Output: ..\..\data\rename\rename-proposal.v1.jsonl
echo To review/apply, use the existing Renamer window: 03_CLASSIFY\RENAME.bat
pause
