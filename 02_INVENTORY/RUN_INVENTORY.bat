@echo off
setlocal
if "%~1"=="" (
  echo Usage: RUN_INVENTORY.bat "PATH"
  exit /b 2
)
pushd "%~dp0.."
python -m engine.registry scan "%~1"
set "INVENTORY_EXIT=%ERRORLEVEL%"
popd
exit /b %INVENTORY_EXIT%

