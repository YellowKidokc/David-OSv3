@echo off
setlocal
cd /d "D:\GitHub\David-OSv3\GUI\theophysics_corpus_indexer"
call "D:\GitHub\David-OSv3\LEAN 4\theophysics_corpus_indexer\.venv\Scripts\activate.bat"
streamlit run app.py
pause
