# scripts/convert_text_to_markdown.py
from __future__ import annotations
import os
from datetime import datetime

SCRIPT_SPEC = {
    "name": "Convert Text → Markdown",
    "version": "1.0.0",
    "description": "Convert plain text files to Markdown with optional title",
    "parameters": {
        "input_text_path": {"type": "path", "default": "", "description": "Text file to convert"},
        "output_md_path": {"type": "string", "default": "", "description": "Output path (blank = same name .md)"},
        "title": {"type": "string", "default": "", "description": "Optional H1 title to add"},
    },
}

def _log(ctx, msg: str) -> None:
    if ctx and hasattr(ctx, "log") and callable(ctx.log):
        ctx.log(msg)
    else:
        print(msg)

def run(config: dict, connection=None) -> dict:
    ctx = connection
    in_path = config.get("input_text_path", "")
    out_path = (config.get("output_md_path") or "").strip()
    title = (config.get("title") or "").strip()
    
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError(f"Input not found: {in_path}")
    
    if not out_path:
        base, _ = os.path.splitext(in_path)
        out_path = base + ".md"
    
    _log(ctx, f"Reading text: {in_path}")
    txt = open(in_path, "r", encoding="utf-8", errors="ignore").read()
    
    md_content = ""
    if title:
        md_content += f"# {title}\n\n"
    md_content += txt.strip() + "\n"
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    _log(ctx, f"Wrote: {out_path}")
    
    return {
        "status": "ok", 
        "output_md_path": out_path, 
        "computed_at": datetime.utcnow().isoformat() + "Z"
    }
