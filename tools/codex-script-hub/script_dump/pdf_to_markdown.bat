@echo off
title PDF to Markdown
cd /d "%~dp0"
if "%~1"=="" (
    python pdf_to_markdown.py
) else (
    python pdf_to_markdown.py %*
)
pause
