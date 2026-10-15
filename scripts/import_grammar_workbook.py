"""One-shot importer: grammar workbook dump -> config/rules/*.json.

Reads the tab-separated dump (grammar.txt) and writes the four rule JSONs.
Idempotent; safe to re-run. Stdlib only.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DUMP = Path(r"C:\Users\David\AppData\Local\Temp\fisxlsx\grammar.txt")
OUT = REPO / "config" / "rules"

SHEETS = {  # sheet name -> (output filename, schema id, id column)
    "Guardrails": ("guardrails.v1.json", "top-ai-fis.guardrails.v1", "guardrail_id"),
    "Actions_Master": ("actions_master.v1.json", "top-ai-fis.actions_master.v1", "action_id"),
    "Action_Conditions": ("action_conditions.v1.json", "top-ai-fis.action_conditions.v1", None),
    "Compatibility_Matrix": ("compatibility_matrix.v1.json", "top-ai-fis.compatibility_matrix.v1", "action_or_signal_a"),
}


def sheet_rows(text: str, sheet: str) -> list[list[str]]:
    marker = f"########## SHEET: {sheet} "
    start = text.index(marker)
    end = text.find("########## SHEET:", start + len(marker))
    block = text[start:end if end > 0 else len(text)]
    rows = [ln.split("\t") for ln in block.splitlines()[1:] if ln.strip()]
    return rows


def keyed(rows: list[list[str]], header_token: str) -> list[dict]:
    hi = next(i for i, r in enumerate(rows) if header_token in [c.strip() for c in r])
    header = [h.strip().lower().replace(" ", "_").replace("/", "_") for h in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        rec = {header[i]: (r[i].strip() if i < len(r) else "") for i in range(len(header))}
        if any(rec.values()):
            out.append(rec)
    return out


def main() -> int:
    text = DUMP.read_text(encoding="utf-8")
    for sheet, (fname, schema, _idcol) in SHEETS.items():
        recs = keyed(sheet_rows(text, sheet), _idcol or "action_id")
        assert recs, f"no rows parsed for {sheet}"
        (OUT / fname).write_text(
            json.dumps({"schema": schema, "source_workbook": "FIS_Rule_Automation_Grammar.xlsx",
                        "records": recs}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"[RULES] {fname}: {len(recs)} records", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
