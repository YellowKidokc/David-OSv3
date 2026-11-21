@echo off
rem Builds the registry page. Drag a folder onto this file, or run it and paste a folder path.
setlocal
set "TARGET=%~1"
if "%TARGET%"=="" set /p "TARGET=Folder to scan: "
python -X utf8 "%~dp0registry_scan.py" "%TARGET%"
if errorlevel 1 (echo. & echo The scan failed. Nothing was changed. & pause & exit /b 1)
for /f "delims=" %%F in ('dir /b /o-d "%~dp0out\*_REGISTRY.html" 2^>nul') do (start "" "%~dp0out\%%F" & goto :done)
:done
endlocal
