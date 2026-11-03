@echo off
:: FIS Startup Installer
:: Registers both FIS daemons as Windows Task Scheduler logon tasks.
:: Run once as normal user (no admin needed for ONLOGON tasks in current user scope).
:: After this runs, both daemons start automatically every time you log in —
:: independently of AutoHotkey or anything else.

set PYTHONW=C:\Users\David\AppData\Local\Programs\Python\Python312\pythonw.exe
set FIS_DIR=D:\DONT TOUCH BOOT UP\FIS

echo.
echo Installing FIS startup tasks...
echo.

:: ── FILE TRACKER ────────────────────────────────────────────────────────────
schtasks /Delete /TN "POF FIS File Tracker" /F >nul 2>&1

schtasks /Create ^
  /TN "POF FIS File Tracker" ^
  /TR "\"%PYTHONW%\" \"%FIS_DIR%\fis_daemon.py\"" ^
  /SC ONLOGON ^
  /DELAY 0:30 ^
  /RL HIGHEST ^
  /F

if %ERRORLEVEL% EQU 0 (
    echo [OK] POF FIS File Tracker registered
) else (
    echo [FAIL] File tracker registration failed
)

:: ── FOLDER TRACKER ──────────────────────────────────────────────────────────
schtasks /Delete /TN "POF FIS Folder Tracker" /F >nul 2>&1

schtasks /Create ^
  /TN "POF FIS Folder Tracker" ^
  /TR "\"%PYTHONW%\" \"%FIS_DIR%\fis_folder_daemon.py\"" ^
  /SC ONLOGON ^
  /DELAY 0:45 ^
  /RL HIGHEST ^
  /F

if %ERRORLEVEL% EQU 0 (
    echo [OK] POF FIS Folder Tracker registered
) else (
    echo [FAIL] Folder tracker registration failed
)

echo.
echo Both tasks set to run 30s and 45s after logon respectively.
echo File tracker:   tracks files,  CHI 12-variable naming schema
echo Folder tracker: tracks folders, symptom/class schema + .fisnote manifests
echo.
echo To verify: schtasks /Query /TN "POF FIS File Tracker"
echo To remove:  schtasks /Delete /TN "POF FIS File Tracker" /F
echo             schtasks /Delete /TN "POF FIS Folder Tracker" /F
echo.
pause
