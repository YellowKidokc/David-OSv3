"""Generate portable Markdown structural indexes alongside a FIS review."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def render(source_name: str, raw: bytes) -> str:
    """Index source bytes without changing the source or assigning authority."""
    text = raw.decode("utf-8-sig", errors="replace")
    headings = []
    blocks = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0][0] and len(marker[1]) >= len(fence[0]) and not marker[2].strip():
                code = "\n".join(fence[2])
                blocks.append((fence[1], len(fence[2]), hashlib.sha256(code.encode()).hexdigest()[:16]))
                fence = None
            else:
                fence[2].append(line)
            continue
        if marker:
            fence = (marker[1], marker[2].strip() or "unknown", [])
            continue
        heading = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$", line)
        if heading:
            headings.append((len(heading[1]), heading[2]))

    sha256 = hashlib.sha256(raw).hexdigest()
    lines = [
        "---",
        "schema: fis.vial.v1",
        f"source: {json.dumps(source_name, ensure_ascii=False)}",
        f"sha256: {sha256}",
        f"size_bytes: {len(raw)}",
        "---",
        "",
        f"# {source_name}",
        "",
        "## Structure",
        "",
        f"- Lines: {len(text.splitlines()):,}",
        f"- Words: {len(text.split()):,}",
        f"- Headings: {len(headings)}",
        f"- Fenced code blocks: {len(blocks)}",
    ]
    if headings:
        lines.extend(["", "## Outline", ""])
        lines.extend(f"{'  ' * (level - 1)}- {title}" for level, title in headings)
    if blocks:
        lines.extend(["", "## Code blocks", ""])
        lines.extend(f"- {lang}, {count} lines, SHA-256 prefix `{digest}`" for lang, count, digest in blocks)
    lines.extend(["", "The source bytes are canonical. This vial is a derived structural index.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not args.output.name.casefold().endswith(".vial.md"):
        parser.error("output must end with .vial.md")
    raw = args.source.read_bytes()
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render(args.source.name, raw))


if __name__ == "__main__":
    main()
