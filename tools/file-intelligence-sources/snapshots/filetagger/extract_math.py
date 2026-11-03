#!/usr/bin/env python3
"""
Math Extractor — pull all equations from HTML articles.
=======================================================
Extracts MathJax ($$...$$, \\(...\\)), eq-box divs, and
code blocks containing math. Outputs JSON with equation,
context, and placeholders for English translation + isomorphism.

Usage:
  python extract_math.py article.html
  python extract_math.py folder/ --recursive
  python extract_math.py folder/ --recursive --output equations.json
"""
import argparse, json, re, sys
from pathlib import Path
from datetime import datetime

def extract_from_html(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    equations = []
    
    # 1. Display math: $$...$$
    for m in re.finditer(r'\$\$(.*?)\$\$', text, re.DOTALL):
        eq = m.group(1).strip()
        if len(eq) > 3:
            ctx = get_context(text, m.start(), 200)
            equations.append({
                "type": "display_math",
                "raw": eq,
                "context": ctx,
                "source": str(path),
            })
    
    # 2. Inline math: \(...\)
    for m in re.finditer(r'\\\((.*?)\\\)', text, re.DOTALL):
        eq = m.group(1).strip()
        if len(eq) > 3:
            ctx = get_context(text, m.start(), 150)
            equations.append({
                "type": "inline_math",
                "raw": eq,
                "context": ctx,
                "source": str(path),
            })
    
    # 3. eq-box divs
    for m in re.finditer(r'<div[^>]*class="[^"]*eq-box[^"]*"[^>]*>(.*?)</div>', text, re.DOTALL):
        content = strip_html(m.group(1)).strip()
        if len(content) > 5:
            equations.append({
                "type": "eq_box",
                "raw": content,
                "context": get_context(text, m.start(), 200),
                "source": str(path),
            })
    
    # 4. Code blocks with math symbols
    for m in re.finditer(r'<code[^>]*>(.*?)</code>', text, re.DOTALL):
        content = strip_html(m.group(1)).strip()
        if any(c in content for c in ['=', '∫', '∂', 'Σ', '→', 'χ', 'Φ', 'ψ', 'log']) and len(content) > 5:
            equations.append({
                "type": "code_math",
                "raw": content,
                "context": get_context(text, m.start(), 150),
                "source": str(path),
            })
    
    # 5. Text patterns: things that look like equations
    for m in re.finditer(r'(?:^|\s)([\w\(\)]+\s*=\s*[^<\n]{5,80})', text):
        eq = m.group(1).strip()
        if any(c in eq for c in ['(', ')', '*', '/', '+', '-', '=']) and not eq.startswith('http'):
            if not any(e["raw"] == eq for e in equations):
                equations.append({
                    "type": "text_equation",
                    "raw": eq,
                    "context": get_context(text, m.start(), 150),
                    "source": str(path),
                })
    
    # Deduplicate
    seen = set()
    unique = []
    for eq in equations:
        key = eq["raw"][:80]
        if key not in seen:
            seen.add(key)
            unique.append(eq)
    
    return unique

def strip_html(text):
    return re.sub(r'<[^>]+>', '', text)

def get_context(text, pos, window):
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    ctx = text[start:end]
    ctx = strip_html(ctx)
    ctx = re.sub(r'\s+', ' ', ctx).strip()
    return ctx[:200]

def build_mtl_template(equations, source):
    """Build Math Translation Layer template for each equation."""
    mtl = []
    for i, eq in enumerate(equations):
        mtl.append({
            "id": f"EQ-{i+1:03d}",
            "source_file": source,
            "type": eq["type"],
            "equation": eq["raw"],
            "context": eq["context"],
            "english_translation": "",      # TO FILL: plain English
            "term_by_term": [],             # TO FILL: each variable explained
            "isomorphism": {
                "physics_side": "",         # TO FILL: physics equation
                "theology_side": "",        # TO FILL: theology mapping
                "shared_structure": "",     # TO FILL: what's the same
            },
            "difficulty": "",               # simple | moderate | advanced
            "law_reference": "",            # which of the 10 Laws
        })
    return mtl

def main():
    ap = argparse.ArgumentParser(description="Extract math from HTML articles")
    ap.add_argument("path", help="HTML file or folder")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--output", "-o", help="Write JSON output")
    ap.add_argument("--mtl", action="store_true", help="Generate MTL templates")
    a = ap.parse_args()

    target = Path(a.path)
    if target.is_file():
        files = [target]
    elif target.is_dir():
        g = target.rglob("*.html") if a.recursive else target.glob("*.html")
        files = sorted([f for f in g if "-wrapped" not in f.stem])
    else:
        print(f"Not found: {a.path}"); return 1

    all_eqs = []
    all_mtl = []
    for f in files:
        eqs = extract_from_html(f)
        all_eqs.extend(eqs)
        if a.mtl:
            all_mtl.extend(build_mtl_template(eqs, str(f)))
        name = f.stem[:40]
        types = {}
        for e in eqs:
            types[e["type"]] = types.get(e["type"], 0) + 1
        type_str = " | ".join(f"{k}:{v}" for k,v in types.items())
        print(f"  {name:40s}  {len(eqs):3d} equations  [{type_str}]")

    print(f"\n  Total: {len(all_eqs)} equations from {len(files)} files")

    if a.output:
        data = {
            "engine": "extract_math v1.0",
            "generated": datetime.now().isoformat(),
            "total_equations": len(all_eqs),
            "files_scanned": len(files),
            "equations": all_eqs,
        }
        if a.mtl:
            data["mtl_templates"] = all_mtl
        Path(a.output).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Output: {a.output}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
