# Lossless Tools

Three Python scripts, no extras.

## Folder Structure

```
lossless-tools/
├── namer.py          # naming system (LOSS__ / MEQ__ internal names)
├── lossless.py       # inbox → compress → outbox pipeline
├── deepseek_call.py  # DeepSeek API wrapper
├── inbox/            # drop files here
├── outbox/           # compressed vials land here
├── done/             # originals move here after processing
└── README.md
```

## Setup

Set your DeepSeek API key:

```
set DEEPSEEK_API_KEY=sk-your-key-here
```

No pip installs needed — uses only Python standard library.

## Usage

### Name a file (no compression)

```
python namer.py myfile.md              # auto-detect LOSS or MEQ
python namer.py myfile.md --mode meq   # force Master Equation naming
```

### Compress one file

```
python lossless.py myfile.md
```

### Process everything in inbox

```
python lossless.py
```

### Watch inbox for new files

```
python lossless.py --watch
```

### Call DeepSeek directly

```
python deepseek_call.py myfile.md
python deepseek_call.py myfile.md --mode meq
```

## Naming Convention

- External filename stays the same (don't rename the file)
- Internal name goes on line 1 as H1: `# LOSS__<slug>__2026-08-12`
- MEQ prefix for Master Equation / Nabla / Theophysics content
- LOSS prefix for everything else
- Auto-detection scans first 100 lines for MEQ keywords
