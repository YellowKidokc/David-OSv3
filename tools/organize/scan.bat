@echo off
title CHI Folder Scanner
cd /d "%~dp0"
echo.
echo  ================================================================
echo   CHI FOLDER SCANNER � Pick folders, scan, export to Excel
echo  ================================================================
echo.

:MENU
echo  Current scanned drives:
python engine.py status 2>nul
echo.
echo  Options:
echo    1. Scan a folder (source)
echo    2. Scan a folder (target)
echo    3. Export to Excel (Review Queue)
echo    4. Run classifier on scanned files
echo    5. Generate .chi sidecars
echo    6. Open Excel workbook
echo    7. Exit
echo.
set /p choice="Pick (1-7): "

if "%choice%"=="1" goto SCAN_SOURCE
if "%choice%"=="2" goto SCAN_TARGET
if "%choice%"=="3" goto EXPORT
if "%choice%"=="4" goto CLASSIFY
if "%choice%"=="5" goto CHI_GEN
if "%choice%"=="6" goto OPEN_EXCEL
if "%choice%"=="7" exit /b

:SCAN_SOURCE
echo.
set /p folder="Folder path: "
set /p role="Role (repo/obsidian/theophysics/html_output/unknown): "
set /p label="Label (short name): "
echo Scanning %folder% as source...
python engine.py scan "%folder%" %role% "%label%"
echo.
goto MENU

:SCAN_TARGET
echo.
set /p folder="Folder path: "
set /p role="Role (repo/obsidian/theophysics/html_output/unknown): "
set /p label="Label (short name): "
echo Scanning %folder% as target...
python engine.py scan "%folder%" %role% "%label%" --target
echo.
goto MENU

:EXPORT
echo.
echo Exporting to Excel...
python classifier.py export
echo.
echo Review Queue exported. Open the workbook to review.
goto MENU

:CLASSIFY
echo.
echo Running classifier on all scanned files...
python classifier.py classify-all
echo.
goto MENU

:CHI_GEN
echo.
set /p folder="Folder to generate .chi sidecars in: "
set /p depth="Depth (default 3): "
if "%depth%"=="" set depth=3
python chi_generator.py scan "%folder%" --update --depth %depth%
echo.
goto MENU

:OPEN_EXCEL
if not defined DAVID_OS_REVIEW_WORKBOOK (
  echo Set DAVID_OS_REVIEW_WORKBOOK to your review workbook path.
) else (
  start "" "%DAVID_OS_REVIEW_WORKBOOK%"
)
goto MENU
