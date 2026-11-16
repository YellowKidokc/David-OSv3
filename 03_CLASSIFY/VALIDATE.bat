@echo off
if "%~1"=="" (
  echo Supply a folder path as the first argument.
  exit /b 2
)
python "%~dp0..\run.py" 03_CLASSIFY/00_SHARED/taxonomy_validator.py "%~1"
exit /b %errorlevel%
