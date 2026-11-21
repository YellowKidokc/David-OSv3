@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist "..\..\.venv\Scripts\python.exe" set "PY=..\..\.venv\Scripts\python.exe"
if not exist "rust\target\release\fis_minhash.exe" (
  where cargo >nul 2>nul && (echo Building Rust accelerator... & pushd rust & cargo build --release -q & popd)
)
echo Fingerprint app  (read-only: never moves, renames or deletes)
set /p FOLDER=Folder to scan: 
if "%FOLDER%"=="" goto :eof
"%PY%" src\run.py "%FOLDER%"
echo Output: ..\..\data\fingerprint\fingerprint.v1.jsonl
pause
