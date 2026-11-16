@echo off
setlocal
cd /d "%~dp0"

echo Classify app  (read-only: never moves, renames or deletes; AI fallback OFF)
set /p FOLDER=Folder or file to classify: 
if "%FOLDER%"=="" goto :eof
set /p ENGINE=Engine [fis/chi] (Enter = fis): 
if "%ENGINE%"=="" set "ENGINE=fis"
python "%~dp0..\..\run.py" apps/classify/src/run.py "%FOLDER%" --engine %ENGINE%
echo Output: ..\..\data\classify\classification.v1.jsonl
pause
