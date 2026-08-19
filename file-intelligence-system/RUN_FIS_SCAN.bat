@echo off
title FIS Folder Brain — Scan and Generate HTML
color 0B
echo.
echo  ================================================================
echo   FIS FOLDER BRAIN v2 — Recursive Semantic Scan
echo   David Lowe / POF 2828
echo  ================================================================
echo.
echo   [1] Cannon folder  (full scan: HTML + fisnotes + local AI)
echo   [2] Cannon folder  (DRY RUN — registry only, nothing written)
echo   [3] Custom path    (full scan)
echo   [4] Cannon folder  (fast — no AI enrichment)
echo   [Q] Quit
echo.
set /p choice="  Select [1/2/3/4/Q]: "

cd /d D:\GitHub\David-OS\file-intelligence-system

if /i "%choice%"=="1" goto cannon
if /i "%choice%"=="2" goto dryrun
if /i "%choice%"=="3" goto custom
if /i "%choice%"=="4" goto fast
if /i "%choice%"=="q" goto end
goto end

:cannon
set "TARGET=\\192.168.2.50\h_hp\Desktop\Cannon"
echo.
echo  Scanning: %TARGET%
echo  Mode: recursive + HTML + fisnotes + local AI (Ollama qwen3:4b)
echo.
python fis_folder_memory.py "%TARGET%" --tree --write --html --file-notes --cleanup-stale
goto done

:fast
set "TARGET=\\192.168.2.50\h_hp\Desktop\Cannon"
echo.
echo  Scanning: %TARGET%  (no AI enrichment)
echo.
python fis_folder_memory.py "%TARGET%" --tree --write --html --file-notes --no-local-ai
goto done

:dryrun
set "TARGET=\\192.168.2.50\h_hp\Desktop\Cannon"
echo.
echo  DRY RUN — registry only, nothing written
echo.
python fis_folder_memory.py "%TARGET%" --tree --no-local-ai
echo.
pause
goto end

:custom
set /p TARGET="  Enter full folder path: "
echo.
echo  Scanning: %TARGET%
echo.
python fis_folder_memory.py "%TARGET%" --tree --write --html --file-notes --cleanup-stale
goto done

:done
echo.
echo  ----------------------------------------------------------------
echo   Done. FIS.html written to target folder and every subfolder.
echo  ----------------------------------------------------------------
echo.
set /p openit="  Open FIS.html now? [Y/N]: "
if /i "%openit%"=="y" start "" "%TARGET%\FIS.html"
pause
goto end

:end
