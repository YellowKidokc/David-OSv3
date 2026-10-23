# Publication Family Tools

This directory holds read-only scanners that group multiple representations of
the same publication without changing source files.

## `near_duplicate_scan.py`

Salvaged from:

`\\192.168.2.50\g_github\D_DRIVE_FULL\GitHub\David-OS\file-intelligence-system\fis_near_dup.py`

Source snapshot date: 2026-08-23. Imported into David-OS v3 on 2026-08-25.

The scanner provides:

- exact SHA-256 duplicate groups;
- shell-stripped Markdown/HTML near-duplicate groups;
- reader-level article families;
- observable presentation-richness comparison;
- CSV/JSON reports and a human-review plan.

Safety boundary:

- explicit `--roots` are required;
- source files are read only;
- output is written only beneath the operator-selected `--out` directory;
- `move_plan_DRAFT.ps1` is fully commented and is never executed;
- presentation richness is a review signal, not canonical authority.

Example:

```powershell
py -3.12 tools\publication_family\near_duplicate_scan.py `
  --roots "D:\corpus" `
  --out "runs\publication-family\pilot"
```

Do not use a generated keeper recommendation as an automatic move, rename,
archive, or deletion decision. Lineage and human review remain required.

## `format_family_report.py`

Salvaged and generalized from the earlier read-only
`dont_touch_html_dup_report.py`. It accepts repeated `--bucket LABEL=PATH`
arguments, compares shell-stripped Markdown/HTML bodies, and reports which
named format buckets are absent from each inferred family. The required
`--out-dir` is rejected if it is inside a source bucket.

```powershell
py -3.12 tools\publication_family\format_family_report.py `
  --bucket "MD=D:\corpus\MD" `
  --bucket "HTML_A=D:\corpus\HTML" `
  --bucket "CANON=D:\corpus\Canon" `
  --out-dir "D:\GitHub\David-OSv3\runs\publication-family\example"
```
