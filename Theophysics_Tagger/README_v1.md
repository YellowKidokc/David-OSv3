# Theophysics Tagger Seed

This is the first C-drive workspace for the tagger idea.

## What is here

- `01_REGISTRY/tag_registry.csv` - 672 seed tags from the Christian-life / doctrine / Theophysics inventory.
- `config.example.json` - default sources and output locations.
- `tools/tagger.py` - scanner that tags documents, paragraphs, and sentences.
- `02_INDEX/` - generated CSV/JSON indexes go here.
- `03_TAGGED/` - optional copied files by primary tag/category go here.

## Safety rule

The scanner is read-only by default. It writes indexes and folder suggestions. It only copies files when you pass `--copy-by-primary-tag`.

## First test

```powershell
python C:\Theophysics_Tagger\tools\tagger.py --source "\\192.168.2.50\h_hp\Desktop\TEN_LAWS_CANONICAL" --limit 50
```

Optional copy mode after reviewing results:

```powershell
python C:\Theophysics_Tagger\tools\tagger.py --source "O:\_Theophysics_v5" --copy-by-primary-tag --limit 500
```

## Naming idea

Call the system **The Convergence Tagger** or **Theophysics Convergence Ledger**. “Unified” can stay as an internal idea, but “convergence” survives hostile review better.
