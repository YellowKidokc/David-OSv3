# Theophysics Convergence Tagger v3

One program that does what the Tagger and filetagger did separately. It **tags documents against
your registry** (the v2 engine, unchanged) and **catalogs and marks files and folders** (from
filetagger / foldertagger / filetagger_daemon). It's read-only unless you pass a write flag.

**Easiest:** double-click `START_TAGGER.bat` to open the window. It has three tabs:

- **Run:** add folders, tick options, then Scan / Watch / Catalog only.
- **Browse:** every tagged document. Filter by text, tag or category, double-click to open, right-click to show in Explorer.
- **Tags:** how many documents each tag landed on. Double-click a tag to browse it.

(v2 is still at `tools/tagger2.py`, and its notes are in `README_v2.md`. v3 uses the same `tagger.db` and the
same registry hash, so everything v2 already tagged is reused, not re-tagged, and `fistag.py` still works.)

## Command line

```powershell
# tag a folder: .md .txt .pdf .docx .html
python C:\Theophysics_Tagger\tools\tagger3.py scan --source "C:\path\to\papers"

# plus: catalog every file of any type and list duplicates
python C:\Theophysics_Tagger\tools\tagger3.py scan --source "C:\path" --catalog

# plus: write a .fmeta beside each document and a .folder.fmeta in each folder
python C:\Theophysics_Tagger\tools\tagger3.py scan --source "C:\path" --write-sidecars --write-folder-markers

# keep re-tagging as files change (Ctrl+C to stop); results go to 02_INDEX\latest_*.csv
python C:\Theophysics_Tagger\tools\tagger3.py watch --source "C:\path" --write-sidecars

# catalog only (no tagging)
python C:\Theophysics_Tagger\tools\tagger3.py catalog --source "D:\Downloads"
```

`--semantic` adds the meaning layer (needs `ollama serve` and `nomic-embed-text`) to any command.

## What v3 adds over v2

| | |
|---|---|
| **PDF / DOCX / HTML** | PDFs are read with PyMuPDF, using text blocks as paragraphs. DOCX headings count as headings, so they get heading weight. HTML has scripts, styles and nav stripped. Extracted text is cached by size and modified time, so a rerun doesn't re-read PDFs, and extraction uses all cores. |
| **File catalog** (`--catalog`) | Every file, any type: size, dates, quick hash (`--full-hash` for sha256), read tier, and keywords for text files the registry didn't tag. Writes `*_catalog.csv` and `*_duplicates.csv`, sorted by space you could reclaim. |
| **Sidecars** (`--write-sidecars`) | `<file>.fmeta` beside each tagged document: primary tag and category, tags, Master Equation variables, scripture refs and duplicates. It's only rewritten when the tags actually change. |
| **Folder markers** (`--write-folder-markers`) | `.folder.fmeta` in each folder that has tagged documents (`--all-folders` for every folder). It holds a `folder_id` that survives moves, plus previous paths and the folder's top categories and tags, rolled up from the documents inside it. Your own `category:` and `notes:` lines are kept. |
| **Watch** | Re-tags a few seconds after anything changes. It ignores its own sidecars, so it never loops. |
| **Window** | `tools/tagger3_gui.py` |

Problems such as empty files or image-only PDFs with no text layer are listed in `*_errors.csv`, not
silently skipped.

## Layers, disambiguation and the gold set

These are unchanged from v2. See `README_v2.md`: stemmed matching, `ambiguous_terms.txt`, `exclusions.csv`,
`category_weights.csv`, scripture extraction, and `gold-template` / `eval` / `tune` (all available
in v3 as subcommands and as buttons in the window).

## Write flags (all off by default)

- `--write-sidecars`, `--write-folder-markers`: add new small files and never touch yours.
- `--copy-by-primary-tag`: copies (never moves) into `03_TAGGED/<category>/<tag>/`.
- `--write-frontmatter`: edits `.md` files by adding an `auto_tags:` list. The window asks before doing this.
