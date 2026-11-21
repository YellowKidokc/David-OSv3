# scripts/convert_markdown_to_html.py
from __future__ import annotations
import os
from datetime import datetime
import markdown

SCRIPT_SPEC = {
    "name": "Convert Markdown → HTML",
    "version": "1.0.0",
    "description": "Convert Markdown files to HTML with optional styling",
    "parameters": {
        "input_md_path": {"type": "path", "default": "", "description": "Markdown file to convert"},
        "output_html_path": {"type": "string", "default": "", "description": "Output HTML path"},
        "template": {"type": "select", "options": ["minimal", "github", "academic"], "default": "minimal"},
        "include_toc": {"type": "bool", "default": False, "description": "Include table of contents"},
    },
}

TEMPLATES = {
    "minimal": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui;max-width:800px;margin:40px auto;padding:0 20px;line-height:1.6}}</style>
</head><body>{content}</body></html>""",
    
    "github": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial;max-width:980px;margin:0 auto;padding:45px}}
code{{background:#f6f8fa;padding:2px 6px;border-radius:3px}}
pre{{background:#f6f8fa;padding:16px;overflow:auto;border-radius:6px}}
h1,h2{{border-bottom:1px solid #eaecef;padding-bottom:0.3em}}
</style></head><body>{content}</body></html>""",
    
    "academic": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:Georgia,serif;max-width:700px;margin:60px auto;padding:0 20px;line-height:1.8;color:#333}}
h1{{font-size:2em;margin-bottom:0.5em}}h2{{font-size:1.5em;margin-top:2em}}
blockquote{{border-left:3px solid #ccc;margin-left:0;padding-left:20px;font-style:italic}}
</style></head><body>{content}</body></html>"""
}

def _log(ctx, msg: str) -> None:
    if ctx and hasattr(ctx, "log") and callable(ctx.log):
        ctx.log(msg)
    else:
        print(msg)

def run(config: dict, connection=None) -> dict:
    ctx = connection
    in_path = config.get("input_md_path", "")
    out_path = (config.get("output_html_path") or "").strip()
    template_name = config.get("template", "minimal")
    include_toc = config.get("include_toc", False)
    
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError(f"Input not found: {in_path}")
    
    if not out_path:
        base, _ = os.path.splitext(in_path)
        out_path = base + ".html"
    
    _log(ctx, f"Reading Markdown: {in_path}")
    md_text = open(in_path, "r", encoding="utf-8", errors="ignore").read()
    
    # Parse frontmatter for title if present
    title = os.path.basename(in_path)
    if md_text.startswith("---"):
        parts = md_text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"\'')
            md_text = parts[2]
    
    # Convert
    extensions = ['fenced_code', 'tables', 'codehilite']
    if include_toc:
        extensions.append('toc')
    
    html_content = markdown.markdown(md_text, extensions=extensions)
    
    template = TEMPLATES.get(template_name, TEMPLATES["minimal"])
    full_html = template.format(title=title, content=html_content)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    
    _log(ctx, f"Wrote HTML: {out_path}")
    
    return {
        "status": "ok",
        "output_html_path": out_path,
        "template": template_name,
        "computed_at": datetime.utcnow().isoformat() + "Z"
    }
