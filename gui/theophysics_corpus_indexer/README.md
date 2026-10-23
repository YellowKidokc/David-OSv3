# Theophysics Corpus Indexer GUI

Streamlit admin interface for the Lean 4 corpus index and the Master Equation sidecar.

## Run

Double-click `run.bat` or, from this folder:

```cmd
D:\GitHub\David-OSv3\LEAN 4\theophysics_corpus_indexer\.venv\Scripts\activate
streamlit run app.py
```

Then open `http://localhost:8501` in a browser.

## What it does

- **Overview:** high-level counts, duplicate ratio, classification percentages, series bar chart.
- **Unclassified review:** scroll through unclassified files, multi-select rows, and assign a series.
- **Folder batch classify:** pick a source root + subfolder, select files, and bulk-assign a series.
- **ME sidecar:** view the governing claim, presentation counts by status/kind, and drift items.

Every manual classification writes a `MANUAL_CLASSIFY` receipt so the change is auditable.
