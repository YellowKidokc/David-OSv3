# 01_SIDECARS

A sidecar is a small file that carries meaning **about** a source file without touching it.
Rules: `../00_SHARED/TAG_TAXONOMY_v0.4.md`, **Part B**.

## Built here

| File | Does |
|---|---|
| `sidecar_report.py` | Reads a sidecars folder and writes `docs/SIDECAR_CLASSIFICATIONS.md` — every card in one page, grouped by standing, plus the cards worth a second look. `../REPORT.bat` runs it and opens the result |
| `docs/SIDECAR_CLASSIFICATIONS.md` | The current classifications of the AXIOM canon sidecars (51 cards). Generated — never edit, re-run |

## The two sidecar layers we use

| Layer | Format | Lives in | Written by |
|---|---|---|---|
| Navigation card | `mim.v1` Markdown, one per paper, human-named | `<folder>\sidecars\` | classifier pass (no script yet — step 3/5) |
| Status record | `canon_status` JSON, named after the exact source file | `<folder>\Sidecars_and_JSON\` | `David-OSv3\engine\canon_sidecar.py` |

Reference example: `\\192.168.2.50\h_hp\Desktop\Folders\AXIOM_CLASSIFICATION_CANON_2026-07-25 (1)\sidecars`

## Sidecar tools that already exist elsewhere (pointed to, not moved — they're live)

| Tool | Where | What it writes |
|---|---|---|
| Canon sidecar creator | `David-OSv3\engine\canon_sidecar.py` | `canon_status` JSON — "freeze what a file was before anything was declared canonical" |
| Canon scan | `David-OSv3\engine\canon_scan.py` | Canonization dispersal + scan |
| File sidecar contract | `David-OSv3\docs\schemas\file-sidecar-contract.md` | Spec for `.fmeta` / `.chi` / `.folder.fmeta` (the FIS file-identity layer) |
| Convergence Tagger v3 | `C:\Theophysics_Tagger\tools\tagger3.py --write-sidecars --write-folder-markers` | `.fmeta` beside each document, `.folder.fmeta` per folder |
| Evidence sidecars | `Research-Acquisition\API_ALL\03_EVIDENCE\backside_SCRIPTS\evidence_sidecars.py` (+ `front_EVIDENCE\SIDECAR_GUIDE.md`, `SIDECAR_CODES.json`) | `.sidecar` cards with short codes (ME, PHYS…) for evidence companions |
| Evidence sidecar station | `Research-Acquisition\API_ALL\API_HOME\stations\38_EVIDENCE_SIDECARS\` | Same, as a pipeline station |

Four formats exist (`mim.v1`, `canon_status`, `.fmeta/.chi`, evidence `.sidecar`). Part B covers the
first two and maps the evidence short codes to tags; `.fmeta/.chi` is the FIS layer and isn't
reconciled with Part B yet.
