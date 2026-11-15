@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Organize History Watcher ===
echo Records new files, renames, moves, and deletes to .orgledger logbooks.
echo Watching: Desktop, Documents, Downloads. Close this window to stop.
echo Master ledger: %USERPROFILE%\.organize_gui\ledger\master.orgledger
echo.

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "VENV_PY=%LOCALAPPDATA%\organize-gui-venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  set "PYTHON_CMD=%VENV_PY%"
) else (
  set "PYTHON_CMD=python"
)

"%PYTHON_CMD%" -m organize.ledger watch ^
  --root "%USERPROFILE%\Desktop" ^
  --root "%USERPROFILE%\Documents" ^
  --root "%USERPROFILE%\Downloads" ^
  --interval 5

echo.
set /p _hold=Watcher stopped. Press Enter to close...
