"""
Power Structure Vault Scanner
David-OS Pipeline Station

Scans the entire Theophysics vault for content related to the 
institutional power structure map. Outputs a manifest mapping 
every relevant file to its institutional nodes with relevance 
scores and matched snippets.

Usage:
  python power_structure_scanner.py
  python power_structure_scanner.py --vault "O:\_Theophysics_v5"
  python power_structure_scanner.py --output "D:\GitHub\David-OS\pipeline\POWER_STRUCTURE_MANIFEST.json"

No dependencies beyond Python stdlib.
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── INSTITUTIONAL NODES AND THEIR SEARCH SIGNATURES ─────────────────────────
# Each node has: id, name, faction, and keyword groups.
# A file matches a node if it contains keywords from ANY group.
# More groups matched = higher relevance score.

NODES = [
    {
        "id": "fed",
        "name": "Federal Reserve",
        "faction": "FIC",
        "keyword_groups": [
            ["federal reserve", "the fed", "fed chairman", "fed chair"],
            ["monetary policy", "money printing", "quantitative easing", "QE"],
            ["interest rate", "rate hike", "rate cut", "fed funds"],
            ["central bank", "central banking"],
            ["fiat currency", "fiat money", "fiat system"],
            ["jekyll island", "mandrake mechanism"],
            ["fractional reserve"],
        ]
    },
    {
        "id": "bis",
        "name": "Bank for International Settlements",
        "faction": "FIC",
        "keyword_groups": [
            ["bank for international settlements", "BIS"],
            ["central bank of central banks"],
            ["basel", "basel accords", "basel III"],
        ]
    },
    {
        "id": "cia",
        "name": "Central Intelligence Agency",
        "faction": "MIC",
        "keyword_groups": [
            ["CIA", "central intelligence agency"],
            ["MKUltra", "MK Ultra", "MK-Ultra"],
            ["operation ajax", "operation mockingbird"],
            ["iran contra", "iran-contra"],
            ["covert operation", "black ops", "black operation"],
            ["regime change"],
            ["deep state"],
            ["intelligence agency", "intelligence community"],
        ]
    },
    {
        "id": "fbi",
        "name": "Federal Bureau of Investigation",
        "faction": "STATE",
        "keyword_groups": [
            ["FBI", "federal bureau of investigation"],
            ["COINTELPRO", "counter intelligence"],
            ["surveillance state", "domestic surveillance"],
            ["J. Edgar Hoover", "Hoover FBI"],
        ]
    },
    {
        "id": "jpmorgan",
        "name": "JP Morgan Chase",
        "faction": "FIC",
        "keyword_groups": [
            ["JP Morgan", "JPMorgan", "Chase bank", "J.P. Morgan"],
            ["Jamie Dimon"],
            ["too big to fail"],
        ]
    },
    {
        "id": "blackrock",
        "name": "BlackRock",
        "faction": "FIC",
        "keyword_groups": [
            ["BlackRock", "Black Rock"],
            ["Larry Fink"],
            ["ESG", "environmental social governance"],
            ["asset management", "assets under management", "AUM"],
            ["index fund", "ETF", "exchange traded fund"],
        ]
    },
    {
        "id": "palantir",
        "name": "Palantir",
        "faction": "TIC",
        "keyword_groups": [
            ["Palantir", "Palunteer"],
            ["Peter Thiel"],
            ["surveillance", "predictive policing"],
            ["data consolidation", "control grid"],
            ["digital ID", "digital identity"],
            ["social credit"],
        ]
    },
    {
        "id": "nvidia",
        "name": "Nvidia",
        "faction": "TIC",
        "keyword_groups": [
            ["Nvidia", "NVDA"],
            ["GPU", "graphics processing"],
            ["Jensen Huang"],
            ["AI chip", "AI chips", "semiconductor"],
        ]
    },
    {
        "id": "openai_anthropic",
        "name": "OpenAI / Anthropic",
        "faction": "TIC",
        "keyword_groups": [
            ["OpenAI", "Open AI"],
            ["Anthropic"],
            ["Sam Altman"],
            ["Dario Amodei"],
            ["ChatGPT", "GPT-4", "GPT-5"],
            ["Claude"],
            ["frontier model", "frontier AI"],
            ["AI safety", "AI alignment"],
            ["AI regulation", "regulate AI"],
        ]
    },
    {
        "id": "mossad",
        "name": "Mossad / Israeli Intelligence",
        "faction": "MIC",
        "keyword_groups": [
            ["Mossad"],
            ["Israeli intelligence"],
            ["Netanyahu"],
            ["Zionist", "Zionism"],
            ["AIPAC"],
            ["Epstein", "Jeffrey Epstein", "Ghislaine Maxwell"],
        ]
    },
    {
        "id": "irgc",
        "name": "IRGC (Iranian Revolutionary Guard)",
        "faction": "MIC",
        "keyword_groups": [
            ["IRGC", "revolutionary guard"],
            ["Iranian revolution"],
            ["Khamenei", "Ayatollah"],
            ["Hezbollah", "Hamas"],
            ["Houthi", "Houthis"],
            ["proxy war", "proxy warfare"],
            ["resistance economy"],
            ["strait of hormuz"],
        ]
    },
    {
        "id": "mic_contractors",
        "name": "Defense Contractors",
        "faction": "MIC",
        "keyword_groups": [
            ["Lockheed Martin", "Lockheed"],
            ["Boeing defense", "Boeing military"],
            ["Raytheon", "Ratheon"],
            ["BAE Systems", "BAE"],
            ["General Dynamics"],
            ["military industrial complex", "military-industrial complex"],
            ["defense contractor", "defense spending"],
            ["arms trade", "weapons trade", "arms deal"],
        ]
    },
    {
        "id": "vatican_bank",
        "name": "Vatican Bank / IOR",
        "faction": "FIC",
        "keyword_groups": [
            ["Vatican bank", "IOR", "Institute for the Works of Religion"],
            ["Vatican", "Holy See"],
            ["Banco Ambrosiano"],
            ["papal", "papacy"],
        ]
    },
    {
        "id": "city_london",
        "name": "City of London Corporation",
        "faction": "FIC",
        "keyword_groups": [
            ["City of London", "Square Mile"],
            ["London Corporation"],
            ["British Empire", "colonial"],
            ["offshore", "tax haven"],
            ["money laundering"],
        ]
    },
    # ── META-NODES (concepts, not specific institutions) ───────────────────
    {
        "id": "debt_system",
        "name": "Debt-Based Financial System",
        "faction": "FIC",
        "keyword_groups": [
            ["debt based", "debt-based"],
            ["usury", "usurious"],
            ["sovereign debt", "national debt"],
            ["petrodollar", "petro dollar", "petro-dollar"],
            ["dollar hegemony", "dollar dominance"],
            ["currency debasement", "debase"],
            ["Ponzi", "ponzi scheme"],
            ["financialization", "securitization"],
            ["bail out", "bailout"],
            ["too big to fail"],
        ]
    },
    {
        "id": "multipolar",
        "name": "Multipolar World Transition",
        "faction": "FIC",
        "keyword_groups": [
            ["multipolar", "multi-polar"],
            ["BRICS"],
            ["de-dollarization", "dedollarization"],
            ["belt and road", "BRI"],
            ["new world order"],
            ["great reset"],
            ["world economic forum", "WEF", "Davos"],
            ["transnational capital"],
        ]
    },
    {
        "id": "surveillance_state",
        "name": "Surveillance / Control Grid",
        "faction": "TIC",
        "keyword_groups": [
            ["surveillance state", "police state"],
            ["CBDC", "central bank digital currency", "programmable money"],
            ["digital ID", "digital identity"],
            ["social credit", "social credit score"],
            ["Snowden", "Edward Snowden"],
            ["NSA", "national security agency"],
            ["PATRIOT Act", "patriot act"],
            ["panopticon"],
            ["facial recognition"],
            ["mass surveillance"],
        ]
    },
    {
        "id": "media_narrative",
        "name": "Media / Narrative Control",
        "faction": "MEDIA",
        "keyword_groups": [
            ["operation mockingbird"],
            ["media control", "controlled media", "media manipulation"],
            ["propaganda", "narrative control", "manufactured consent"],
            ["false flag", "false-flag"],
            ["psyop", "psychological operation"],
            ["censorship", "information control"],
            ["fake news"],
        ]
    },
    {
        "id": "entropy_civilizational",
        "name": "Civilizational Entropy / Decay",
        "faction": "FRAMEWORK",
        "keyword_groups": [
            ["civilizational decay", "civilizational collapse"],
            ["semantic collapse", "semantic rot"],
            ["coherence metric", "coherence decay"],
            ["phase transition"],
            ["nucleation"],
            ["anti-property", "anti-properties", "anti-fruit"],
            ["moral conservation"],
            ["entropy cascade"],
            ["K-shaped", "K shaped economy"],
            ["wealth inequality"],
        ]
    },
]

# ── SKIP PATTERNS ──────────────────────────────────────────────────────────
SKIP_DIRS = {
    '.git', '.obsidian', '.smart-env', '.stversions', '.stfolder',
    '.claudian', '.claude', '__pycache__', 'node_modules',
    'ZZZ_DUPLICATES', '_ARCHIVE', '00_ARCHIVE',
}

SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico',
    '.pdf', '.zip', '.7z', '.rar', '.tar', '.gz',
    '.mp3', '.mp4', '.wav', '.mov', '.avi',
    '.exe', '.dll', '.so', '.pyc', '.pyo',
    '.sqlite', '.sqlite3', '.db',
    '.canvas', '.css',
}


def should_skip(path: Path) -> bool:
    if any(skip in path.parts for skip in SKIP_DIRS):
        return True
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    return False


def scan_file(filepath: Path, nodes: list) -> list:
    """Scan a single file against all nodes. Return list of matches."""
    try:
        text = filepath.read_text(encoding='utf-8', errors='replace')
    except (OSError, PermissionError):
        return []

    if len(text) < 50:
        return []

    text_lower = text.lower()
    matches = []

    for node in nodes:
        groups_matched = 0
        matched_keywords = []
        snippets = []

        for group in node["keyword_groups"]:
            group_hit = False
            for keyword in group:
                kw_lower = keyword.lower()
                # Use word boundary for short keywords to avoid false positives
                if len(keyword) <= 3:
                    pattern = r'\b' + re.escape(kw_lower) + r'\b'
                    if re.search(pattern, text_lower):
                        group_hit = True
                        matched_keywords.append(keyword)
                        # Extract snippet
                        idx = text_lower.find(kw_lower)
                        if idx >= 0:
                            start = max(0, idx - 80)
                            end = min(len(text), idx + len(keyword) + 80)
                            snippet = text[start:end].replace('\n', ' ').strip()
                            if snippet and len(snippets) < 3:
                                snippets.append(snippet)
                else:
                    if kw_lower in text_lower:
                        group_hit = True
                        matched_keywords.append(keyword)
                        idx = text_lower.find(kw_lower)
                        if idx >= 0:
                            start = max(0, idx - 80)
                            end = min(len(text), idx + len(keyword) + 80)
                            snippet = text[start:end].replace('\n', ' ').strip()
                            if snippet and len(snippets) < 3:
                                snippets.append(snippet)
                if group_hit:
                    break  # One hit per group is enough

            if group_hit:
                groups_matched += 1

        if groups_matched > 0:
            # Relevance score: more keyword groups matched = higher score
            total_groups = len(node["keyword_groups"])
            relevance = round(groups_matched / total_groups, 2)
            # Count total keyword occurrences for density
            density = sum(text_lower.count(kw.lower()) for kw in matched_keywords)

            matches.append({
                "node_id": node["id"],
                "node_name": node["name"],
                "faction": node["faction"],
                "groups_matched": groups_matched,
                "total_groups": total_groups,
                "relevance": relevance,
                "density": density,
                "matched_keywords": list(set(matched_keywords)),
                "snippets": snippets[:3],
            })

    return matches


def scan_vault(vault_root: str, output_path: str = None):
    """Scan entire vault and produce manifest."""
    root = Path(vault_root)
    if not root.exists():
        print(f"ERROR: Vault not found at {vault_root}")
        sys.exit(1)

    print(f"Scanning vault: {root}")
    print(f"Nodes to match: {len(NODES)}")

    # Collect all scannable files
    all_files = []
    for path in root.rglob('*'):
        if path.is_file() and not should_skip(path):
            all_files.append(path)

    print(f"Files to scan: {len(all_files)}")

    # Scan
    manifest = {
        "scan_date": datetime.now().isoformat(),
        "vault_root": str(root),
        "total_files_scanned": len(all_files),
        "nodes_searched": len(NODES),
        "files": [],
        "node_summaries": {},
    }

    node_file_counts = defaultdict(int)
    node_top_files = defaultdict(list)
    files_with_matches = 0

    for i, filepath in enumerate(all_files):
        if i % 500 == 0 and i > 0:
            print(f"  Scanned {i}/{len(all_files)} files...")

        matches = scan_file(filepath, NODES)
        if matches:
            files_with_matches += 1
            rel_path = str(filepath.relative_to(root))

            file_entry = {
                "path": rel_path,
                "filename": filepath.name,
                "matches": matches,
                "total_nodes_matched": len(matches),
                "max_relevance": max(m["relevance"] for m in matches),
            }
            manifest["files"].append(file_entry)

            for match in matches:
                nid = match["node_id"]
                node_file_counts[nid] += 1
                node_top_files[nid].append({
                    "path": rel_path,
                    "relevance": match["relevance"],
                    "density": match["density"],
                    "keywords": match["matched_keywords"],
                })

    # Sort each node's files by relevance then density
    for nid in node_top_files:
        node_top_files[nid].sort(key=lambda x: (x["relevance"], x["density"]), reverse=True)
        # Keep top 30 per node
        node_top_files[nid] = node_top_files[nid][:30]

    # Build node summaries
    for node in NODES:
        nid = node["id"]
        manifest["node_summaries"][nid] = {
            "name": node["name"],
            "faction": node["faction"],
            "total_files": node_file_counts.get(nid, 0),
            "top_files": node_top_files.get(nid, []),
        }

    # Sort manifest files by max relevance
    manifest["files"].sort(key=lambda x: x["max_relevance"], reverse=True)

    # Stats
    manifest["stats"] = {
        "files_with_matches": files_with_matches,
        "files_without_matches": len(all_files) - files_with_matches,
        "match_rate": round(files_with_matches / len(all_files) * 100, 1) if all_files else 0,
        "nodes_with_hits": sum(1 for nid in node_file_counts if node_file_counts[nid] > 0),
        "nodes_without_hits": len(NODES) - sum(1 for nid in node_file_counts if node_file_counts[nid] > 0),
    }

    # Output
    if not output_path:
        output_path = str(Path(__file__).parent / "POWER_STRUCTURE_MANIFEST.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*60}")
    print(f"SCAN COMPLETE")
    print(f"{'='*60}")
    print(f"Files scanned:      {len(all_files)}")
    print(f"Files with matches: {files_with_matches} ({manifest['stats']['match_rate']}%)")
    print(f"Nodes with hits:    {manifest['stats']['nodes_with_hits']}/{len(NODES)}")
    print(f"\nTOP NODES BY FILE COUNT:")
    sorted_nodes = sorted(node_file_counts.items(), key=lambda x: x[1], reverse=True)
    for nid, count in sorted_nodes[:15]:
        node = next(n for n in NODES if n["id"] == nid)
        print(f"  {node['name']:45s} [{node['faction']:6s}]  {count:>5d} files")

    print(f"\nManifest written to: {output_path}")
    print(f"Feed this manifest to Kimi to build the drill-down pages.")

    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Scan Theophysics vault for power structure content")
    parser.add_argument("--vault", default=r"O:\_Theophysics_v5", help="Vault root path")
    parser.add_argument("--output", default=None, help="Output manifest path")
    args = parser.parse_args()

    scan_vault(args.vault, args.output)
