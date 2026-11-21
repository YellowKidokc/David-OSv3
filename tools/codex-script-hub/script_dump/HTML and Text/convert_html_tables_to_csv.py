# scripts/convert_html_tables_to_csv.py
from __future__ import annotations
import os
from datetime import datetime
import pandas as pd

SCRIPT_SPEC = {
    "name": "Extract HTML Tables → CSV",
    "version": "1.0.0",
    "description": "Extract tables from HTML files and save as CSV",
    "parameters": {
        "input_html_path": {"type": "path", "default": "", "description": "HTML file with tables"},
        "table_index": {"type": "int", "default": 0, "min": 0, "max": 999, "description": "Which table (0=first)"},
        "output_csv_path": {"type": "string", "default": "", "description": "Output CSV path"},
    },
}

def _log(ctx, msg: str) -> None:
    if ctx and hasattr(ctx, "log") and callable(ctx.log):
        ctx.log(msg)
    else:
        print(msg)

def run(config: dict, connection=None) -> dict:
    ctx = connection
    in_path = config.get("input_html_path", "")
    idx = int(config.get("table_index", 0))
    out_path = (config.get("output_csv_path") or "").strip()
    
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError(f"Input not found: {in_path}")
    
    if not out_path:
        base, _ = os.path.splitext(in_path)
        out_path = f"{base}_table_{idx}.csv"
    
    _log(ctx, f"Reading HTML tables: {in_path}")
    tables = pd.read_html(in_path)
    
    if idx >= len(tables):
        raise IndexError(f"table_index {idx} out of range. Found {len(tables)} tables.")
    
    df = tables[idx]
    df.to_csv(out_path, index=False)
    _log(ctx, f"Wrote CSV: {out_path} ({len(df)} rows)")
    
    return {
        "status": "ok",
        "tables_found": len(tables),
        "table_index": idx,
        "rows": int(len(df)),
        "output_csv_path": out_path,
        "computed_at": datetime.utcnow().isoformat() + "Z",
    }
