@echo off
title CHI Nightly Scan
cd /d "D:\DONT TOUCH BOOT UP\organize"

echo [%date% %time%] Starting nightly chi scan...

python chi_generator.py scan "D:\DONT TOUCH BOOT UP" --update --depth 2
python chi_generator.py scan D:\LOGOS_V5 --update --depth 3
python chi_generator.py scan D:\BIL --update --depth 2

python classifier.py train

python engine.py scan "D:\DONT TOUCH BOOT UP" repo dev

echo [%date% %time%] Nightly scan complete.
