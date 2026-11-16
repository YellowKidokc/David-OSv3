@echo off
python "%~dp0..\..\run.py" -m fis serve %*
exit /b %errorlevel%
