#!/usr/bin/env python3
"""
PDF to Markdown Converter
Purpose: Convert PDF files to clean markdown. Supports drag-and-drop,
         file picker, and folder batch mode.
Date: 2026-08-16
Author: codex
Status: TESTED (pymupdf required: pip install pymupdf)
"""

import sys
import os
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    print("ERROR: pymupdf not installed. Run:  pip install pymupdf")
    input("Press Enter to exit...")
    sys.exit(1)


def pdf_to_markdown(pdf_path: Path, output_dir: Path | None = None) -> Path:
    """Convert a single PDF to markdown. Returns the output path."""
    doc = fitz.open(str(pdf_path))
    lines = []
    lines.append(f"# {pdf_path.stem}\n")
    lines.append(f"*Source: {pdf_path.name}*\n")
    lines.append(f"*Pages: {len(doc)}*\n")
    lines.append("---\n")

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            lines.append(f"\n## Page {page_num + 1}\n")
            # Clean up the text
            cleaned = []
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped:
                    cleaned.append(stripped)
            lines.append("\n".join(cleaned))
            lines.append("")

    doc.close()

    # Determine output path
    if output_dir is None:
        output_dir = pdf_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{pdf_path.stem}.md"

    # Avoid overwriting
    counter = 1
    while out_path.exists():
        out_path = output_dir / f"{pdf_path.stem}_{counter}.md"
        counter += 1

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def convert_batch(paths: list[str], output_dir: Path | None = None):
    """Convert multiple PDFs."""
    results = []
    for p in paths:
        path = Path(p.strip().strip('"'))
        if not path.exists():
            print(f"  SKIP (not found): {path}")
            continue
        if path.is_dir():
            pdfs = list(path.glob("*.pdf"))
            if not pdfs:
                print(f"  SKIP (no PDFs in): {path}")
                continue
            for pdf in pdfs:
                try:
                    out = pdf_to_markdown(pdf, output_dir)
                    print(f"  OK: {pdf.name} -> {out}")
                    results.append(out)
                except Exception as e:
                    print(f"  FAIL: {pdf.name} -> {e}")
        elif path.suffix.lower() == ".pdf":
            try:
                out = pdf_to_markdown(path, output_dir)
                print(f"  OK: {path.name} -> {out}")
                results.append(out)
            except Exception as e:
                print(f"  FAIL: {path.name} -> {e}")
        else:
            print(f"  SKIP (not a PDF): {path}")
    return results


def interactive_mode():
    """File picker mode when no args given."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()

        print("PDF to Markdown Converter")
        print("=" * 40)
        print("[1] Select PDF file(s)")
        print("[2] Select a folder (convert all PDFs)")
        print("[3] Paste path(s) manually")
        print()
        choice = input("Choose (1/2/3): ").strip()

        output_dir = None
        ask_output = input("Custom output folder? (y/n, default=same folder): ").strip().lower()
        if ask_output == "y":
            output_dir = filedialog.askdirectory(title="Choose output folder")
            if output_dir:
                output_dir = Path(output_dir)
                print(f"  Output -> {output_dir}")
            else:
                output_dir = None

        if choice == "1":
            files = filedialog.askopenfilenames(
                title="Select PDF(s)",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
            )
            if files:
                convert_batch(list(files), output_dir)
            else:
                print("No files selected.")
        elif choice == "2":
            folder = filedialog.askdirectory(title="Select folder with PDFs")
            if folder:
                convert_batch([folder], output_dir)
            else:
                print("No folder selected.")
        elif choice == "3":
            print("Paste path(s), one per line. Empty line to start:")
            paths = []
            while True:
                line = input().strip()
                if not line:
                    break
                paths.append(line)
            if paths:
                convert_batch(paths, output_dir)
        else:
            print("Invalid choice.")

        root.destroy()
    except ImportError:
        # No tkinter, fall back to manual input
        print("PDF to Markdown Converter (no GUI available)")
        print("Paste PDF path(s), one per line. Empty line to start:")
        paths = []
        while True:
            line = input().strip()
            if not line:
                break
            paths.append(line)
        if paths:
            convert_batch(paths)

    input("\nDone. Press Enter to exit...")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Drag-and-drop or command line mode
        print("PDF to Markdown Converter")
        print("=" * 40)
        print(f"Processing {len(sys.argv) - 1} item(s)...")
        convert_batch(sys.argv[1:])
        input("\nDone. Press Enter to exit...")
    else:
        interactive_mode()
