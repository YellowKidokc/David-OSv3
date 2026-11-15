# scripts/convert_html_to_markdown.py
from __future__ import annotations
import os
from datetime import datetime
from markdownify import markdownify as md

SCRIPT_SPEC = {
    "name": "Convert HTML → Markdown",
    "version": "1.0.0",
    "description": "Convert HTML files to clean Markdown format",
    "parameters": {
        "input_html_path": {"type": "path", "default": "", "description": "HTML file to convert"},
        "output_md_path": {"type": "string", "default": "", "description": "Output path (blank = same name .md)"},
        "strip": {"type": "bool", "default": True, "description": "Strip extra whitespace"},
    },
}

def _log(ctx, msg: str) -> None:
    if ctx and hasattr(ctx, "log") and callable(ctx.log):
        ctx.log(msg)
    else:
        print(msg)

def run(config: dict, connection=None) -> dict:
    ctx = connection  # For compatibility
    in_path = config.get("input_html_path", "")
    out_path = (config.get("output_md_path") or "").strip()
    strip = bool(config.get("strip", True))
    
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError(f"Input not found: {in_path}")
    
    if not out_path:
        base, _ = os.path.splitext(in_path)
        out_path = base + ".md"
    
    _log(ctx, f"Reading HTML: {in_path}")
    html = open(in_path, "r", encoding="utf-8", errors="ignore").read()
    
    _log(ctx, "Converting to Markdown")
    markdown = md(html)
    
    if strip:
        markdown = markdown.strip() + "\n"
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    
    return {
        "status": "ok", 
        "output_md_path": out_path, 
        "computed_at": datetime.utcnow().isoformat() + "Z"
    }
