@echo off
python "%~dp0..\..\run.py" -m streamlit run gui/theophysics_corpus_indexer/app.py %*
exit /b %errorlevel%
