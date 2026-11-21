@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist "..\..\.venv\Scripts\python.exe" set "PY=..\..\.venv\Scripts\python.exe"
echo Classify app  (read-only: never moves, renames or deletes; AI fallback OFF)
set /p FOLDER=Folder or file to classify: 
if "%FOLDER%"=="" goto :eof
set /p ENGINE=Engine [fis/chi] (Enter = fis): 
if "%ENGINE%"=="" set "ENGINE=fis"
"%PY%" src\run.py "%FOLDER%" --engine %ENGINE%
echo Output: ..\..\data\classify\classification.v1.jsonl
pause
