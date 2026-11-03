@echo off
REM ============================================================
REM  Restart the FIS file + folder trackers.
REM
REM  Use this after editing fis_daemon.py / fis_folder_daemon.py,
REM  or any time fis_status.json has gone stale (it is rewritten
REM  every 30s while the daemons are alive).
REM
REM  Logs rotate at 20 MB x 3 backups, so they can no longer grow
REM  without bound the way fis.log and fis_folder.log once did.
REM ============================================================
REM  Autostart at logon is handled by the HKCU Run keys
REM  POF_FIS_FileTracker / POF_FIS_FolderTracker. Do NOT also add a
REM  Startup-folder shortcut for these, or you get two of each daemon.
setlocal
set PYW=C:\Users\David\AppData\Local\Programs\Python\Python312\pythonw.exe
cd /d "%~dp0"

echo Stopping any running FIS daemons ...
REM  Match on the script path in the command line — pythonw has no window
REM  title, so a WINDOWTITLE filter would silently match nothing and leave
REM  the old daemons running alongside the new ones.
for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*fis_daemon.py*' -or $_.CommandLine -like '*fis_folder_daemon.py*' } | Select-Object -ExpandProperty ProcessId"`) do (
    echo   stopping pid %%P
    taskkill /f /pid %%P >nul 2>&1
)

echo Starting file tracker ...
start "" "%PYW%" "%~dp0fis_daemon.py"

echo Starting folder tracker ...
start "" "%PYW%" "%~dp0fis_folder_daemon.py"

echo.
echo Both daemons launched. Give them 30s, then check:
echo   fis_status.json / fis_folder_status.json  ("updated_at" should be current)
endlocal
