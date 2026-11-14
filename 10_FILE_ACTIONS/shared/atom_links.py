"""atom_links.py — Generate Obsidian wikilink vaults from atom match data.

RULE: Never writes into any existing vault. Generates a fresh standalone vault
that can be opened separately in Obsidian. Each paper gets one .md file with
its atom-based links. The source papers are referenced by wikilink but never modified.

Output structure:
    <output_vault>/
        .obsidian/              (minimal config so Obsidian recognizes it)
        _INDEX.md               (graph summary: how many docs, edges, clusters)
        _BY_LAW/                (one index per law: which papers touch that law)
        papers/                 (one .md per paper with Related Papers section)

Each paper file contains:
    - Title and source path (so you can find the original)
    - Attention vector top terms (what this paper is about)
    - Law signals (which laws it touches)
    - Related Papers as [[wikilinks]] with shared atom count and reason
    - Family membership if any

Usage:
    python atom_links.py build REPORT_DIR --output VAULT_PATH --threshold 10
    python atom_links.py build REPORT_DIR --output VAULT_PATH --threshold 10 --dry-run
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_db import ScanDB


def _slug(name: str) -> str:
    """Make a safe Obsidian filename from a paper name."""
    stem = Path(name).stem
    # Keep alphanumeric, hyphens, underscores, spaces
    slug = re.sub(r"[^\w\s\-]", "", stem)
    slug = re.sub(r"\s+", " ", slug).strip()
    return slug[:120] if slug else "unnamed"


def build_vault(report_dir: Path, output_vault: Path, threshold: int = 10,
                scan_db_path: Path | None = None, dry_run: bool = False) -> dict:
    """Build a standalone Obsidian vault of atom-based links."""
    # Load data
    match_path = report_dir / "atom_match_ALL_report.json"
    if not match_path.exists():
        match_path = report_dir / "atom_match_report.json"
    matches_data = json.loads(match_path.read_text(encoding="utf-8"))
    matches = [m for m in matches_data["matches"] if m["shared_atoms"] >= threshold]

    # Load scan DB for card metadata
    db_path = scan_db_path or report_dir / "scans.db"
    db = ScanDB(db_path) if db_path.exists() else None

    # Load attention vectors if available
    att_path = report_dir / "attention" / "attention_vectors.json"
    attention = json.loads(att_path.read_text(encoding="utf-8")) if att_path.exists() else {}

    # Build adjacency: path -> [(other_path, shared_count)]
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    all_docs: set[str] = set()
    for m in matches:
        adjacency[m["path_a"]].append((m["path_b"], m["shared_atoms"]))
        adjacency[m["path_b"]].append((m["path_a"], m["shared_atoms"]))
        all_docs.add(m["path_a"])
        all_docs.add(m["path_b"])

    # Sort each adjacency list by shared count descending
    for path in adjacency:
        adjacency[path].sort(key=lambda x: -x[1])

    # Get card metadata from DB
    cards = {}
    if db:
        for path in all_docs:
            rows = db.conn.execute(
                "SELECT * FROM cards WHERE path = ? ORDER BY rowid DESC LIMIT 1",
                (path,)).fetchall()
            if rows:
                cards[path] = dict(rows[0])

    # Map path -> slug (handle collisions)
    slug_map: dict[str, str] = {}
    used_slugs: dict[str, str] = {}
    for path in sorted(all_docs):
        base = _slug(Path(path).name)
        slug = base
        n = 2
        while slug in used_slugs and used_slugs[slug] != path:
            slug = f"{base}_{n}"
            n += 1
        slug_map[path] = slug
        used_slugs[slug] = path

    stats = {
        "threshold": threshold,
        "documents": len(all_docs),
        "edges": len(matches),
        "avg_connections": round(sum(len(v) for v in adjacency.values()) / max(len(adjacency), 1), 1),
    }

    if dry_run:
        print(f"DRY RUN — would create vault at {output_vault}")
        print(f"  Documents: {stats['documents']}")
        print(f"  Edges (>= {threshold} shared): {stats['edges']}")
        print(f"  Avg connections per doc: {stats['avg_connections']}")
        top = sorted(adjacency.items(), key=lambda x: -len(x[1]))[:10]
        print(f"\n  Most connected:")
        for path, neighbors in top:
            print(f"    {Path(path).name[:50]:50s} {len(neighbors):3d} links")
        return stats

    # Create vault structure
    vault = output_vault
    vault.mkdir(parents=True, exist_ok=True)
    (vault / ".obsidian").mkdir(exist_ok=True)
    # Minimal Obsidian config
    (vault / ".obsidian" / "app.json").write_text('{"showLineNumber": true}', encoding="utf-8")
    (vault / "papers").mkdir(exist_ok=True)
    (vault / "_BY_LAW").mkdir(exist_ok=True)

    # Write each paper file
    law_index: dict[str, list[str]] = defaultdict(list)  # law -> [slugs]

    for path in sorted(all_docs):
        slug = slug_map[path]
        card = cards.get(path, {})
        att = attention.get(path, {})
        neighbors = adjacency.get(path, [])

        lines = []
        lines.append(f"# {Path(path).stem}")
        lines.append("")
        lines.append(f"**Source:** `{path}`")
        if card:
            lines.append(f"**Domain:** {card.get('domain', '?')}  |  **Type:** {card.get('doc_type', '?')}  |  **Confidence:** {card.get('identity_confidence', 0):.0%}")
            if card.get("family_name"):
                lines.append(f"**Family:** {card['family_name']}  (position {card.get('position_in_family', '?')})")
        lines.append("")

        # Attention terms
        if att.get("terms"):
            top_terms = [t[0] for t in att["terms"][:15]]
            lines.append(f"**Key terms:** {', '.join(top_terms)}")
            lines.append("")

        # Law signals
        if att.get("law_signals"):
            signals = att["law_signals"]
            for law in sorted(signals, key=lambda l: -signals[l]):
                lines.append(f"- **{law}**: {signals[law]:.3f}")
                law_index[law].append(slug)
            lines.append("")

        # Related papers
        if neighbors:
            lines.append(f"## Related Papers ({len(neighbors)} connections)")
            lines.append("")
            for other_path, shared in neighbors:
                other_slug = slug_map.get(other_path, _slug(Path(other_path).name))
                other_card = cards.get(other_path, {})
                other_domain = other_card.get("domain", "")
                other_type = other_card.get("doc_type", "")
                meta = f" ({other_type}, {other_domain})" if other_type else ""
                lines.append(f"- [[{other_slug}]] — **{shared} shared atoms**{meta}")
            lines.append("")

        (vault / "papers" / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")

    # Write law index files
    for law, slugs in sorted(law_index.items()):
        lines = [f"# {law}", "", f"{len(set(slugs))} papers touch this law:", ""]
        for s in sorted(set(slugs)):
            lines.append(f"- [[{s}]]")
        (vault / "_BY_LAW" / f"{law}.md").write_text("\n".join(lines), encoding="utf-8")

    # Write index
    top_connected = sorted(adjacency.items(), key=lambda x: -len(x[1]))[:20]
    lines = [
        "# Atom Link Graph",
        "",
        f"**Threshold:** {threshold} shared atoms minimum",
        f"**Documents:** {stats['documents']}",
        f"**Edges:** {stats['edges']}",
        f"**Avg connections:** {stats['avg_connections']}",
        "",
        "## Most Connected Papers",
        "",
    ]
    for path, neighbors in top_connected:
        slug = slug_map[path]
        lines.append(f"- [[{slug}]] — {len(neighbors)} connections")
    lines.append("")
    lines.append("## Law Coverage")
    lines.append("")
    for law in sorted(law_index, key=lambda l: -len(set(law_index[l]))):
        lines.append(f"- [[_BY_LAW/{law}|{law}]] — {len(set(law_index[law]))} papers")

    (vault / "_INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Vault written to {vault}")
    print(f"  Documents: {stats['documents']}")
    print(f"  Edges: {stats['edges']}")
    print(f"  Paper files: {len(all_docs)}")
    print(f"  Law indices: {len(law_index)}")

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build Obsidian vault from atom matches")
    sub = parser.add_subparsers(dest="command")

    build_p = sub.add_parser("build")
    build_p.add_argument("report_dir", type=Path)
    build_p.add_argument("--output", type=Path, required=True, help="Path for the new vault")
    build_p.add_argument("--threshold", type=int, default=10)
    build_p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.command == "build":
        build_vault(args.report_dir, args.output, args.threshold, dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
