@echo off
setlocal
cd /d "%~dp0"

if not exist "rust\target\release\fis_minhash.exe" (
  where cargo >nul 2>nul && (echo Building Rust accelerator... & pushd rust & cargo build --release -q & popd)
)
echo Fingerprint app  (read-only: never moves, renames or deletes)
set /p FOLDER=Folder to scan: 
if "%FOLDER%"=="" goto :eof
python "%~dp0..\..\run.py" apps/fingerprint/src/run.py "%FOLDER%"
echo Output: ..\..\data\fingerprint\fingerprint.v1.jsonl
pause
