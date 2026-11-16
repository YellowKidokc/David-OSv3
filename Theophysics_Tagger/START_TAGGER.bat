@echo off
python "%~dp0..\run.py" -m Theophysics_Tagger.tools.tagger3_gui %*
exit /b %errorlevel%
