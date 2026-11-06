@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
:menu
cls
echo ==============================
echo   David-OS  -  App Launcher
echo ==============================
set i=0
for /d %%A in (apps\*) do (
  set /a i+=1
  set "app!i!=%%~nxA"
  echo   !i!. %%~nxA
)
echo   Q. Quit
echo.
set /p pick=Pick an app: 
if /i "%pick%"=="Q" exit /b
if not defined app%pick% goto menu
call "apps\!app%pick%!\START.bat"
goto menu
