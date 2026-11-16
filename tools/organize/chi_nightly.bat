@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Supply the folder to scan as the first argument.
  exit /b 2
)
python chi_generator.py scan "%~1" --update --depth 2
if errorlevel 1 exit /b %errorlevel%
python classifier.py train
python engine.py scan "%~1" repo dev
exit /b %errorlevel%
