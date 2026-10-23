@echo off
rem 03_CLASSIFY - check a sidecars folder against TAG_TAXONOMY_v0.4. Drag a sidecars folder onto this file.
rem The validator needs nothing but Python (engines are only used by REVIEW.bat).
cd /d "%~dp0"
if "%~1"=="" (
  python 00_SHARED\taxonomy_validator.py "\\192.168.2.50\h_hp\Desktop\Folders\AXIOM_CLASSIFICATION_CANON_2026-07-25 (1)\sidecars"
) else (
  python 00_SHARED\taxonomy_validator.py "%~1"
)
pause
