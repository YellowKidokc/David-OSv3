@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Organize GUI Launcher ===
echo Repo: %CD%
echo.

set "EXITCODE=0"
set "PYTHON_CMD=python"
python --version >nul 2>nul
if errorlevel 1 (
  py -3 --version >nul 2>nul
  if errorlevel 1 (
    echo Python was not found. Install Python 3.9+ and run this again.
    set "EXITCODE=1"
    goto hold
  )
  set "PYTHON_CMD=py -3"
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Checking tkinter in base Python...
%PYTHON_CMD% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo tkinter is not available in this Python install.
  echo Install the standard Python distribution from python.org with Tcl/Tk enabled.
  set "EXITCODE=1"
  goto hold
)

set "VENV_DIR=%LOCALAPPDATA%\organize-gui-venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo Creating GUI virtual environment at "%VENV_DIR%"...
  %PYTHON_CMD% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo Virtual environment creation failed. Read the error above.
    set "EXITCODE=1"
    goto hold
  )
)

echo Checking organize dependencies in GUI virtual environment...
"%VENV_PY%" -c "import tkinter, yaml, pydantic, docopt, rich, jinja2, simplematch" >nul 2>nul
if errorlevel 1 (
  echo Missing package dependencies. Attempting editable install into GUI virtual environment...
  "%VENV_PY%" -m pip install -e .
  if errorlevel 1 (
    echo Dependency install failed. Read the error above.
    set "EXITCODE=1"
    goto hold
  )
)

echo Launching GUI...

REM --- Start FIS API if not already running ---
echo Start the canonical FIS service with python run.py -m fis serve if needed.
echo.

"%VENV_PY%" -m organize.gui %*
set "EXITCODE=%ERRORLEVEL%"
echo.
echo GUI exited with code %EXITCODE%.

:hold
echo.
if "%ORGANIZE_GUI_SKIP_HOLD%"=="1" exit /b %EXITCODE%
set /p _organize_hold=Press Enter to close this window...
exit /b %EXITCODE%
