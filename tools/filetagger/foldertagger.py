"""Compatibility CLI for Tagger v3's legacy folder-marker format."""
import runpy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == '__main__':
    runpy.run_path(str(ROOT/'Theophysics_Tagger/tools/ext_filetagger/legacy_folder_markers.py'), run_name='__main__')
