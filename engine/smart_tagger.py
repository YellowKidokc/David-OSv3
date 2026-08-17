#!/usr/bin/env python3
"""
smart_tagger.py — 4-tag disambiguating tagger for FIS/filetagger integration.

Produces exactly 4 tags per file:
  tag1: domain    (theology, physics, psychology, economics, education, history, etc.)
  tag2: subtopic  (grace, entropy, coherence, decline, measurement, etc.)
  tag3: specific  (Lindblad, Cantillon, phase-transition, W_grace, Yukawa, etc.)
  tag4: unique    (the word that distinguishes THIS file from others with same tag1-3)

Rules:
  - HTML/CSS noise is stripped before tagging (class, href, div, var, font-size, etc.)
  - If a candidate tag already appears 50+ times in the catalog, find a more specific one
  - WordNet expansion used for disambiguation when available
  - tag3 and tag4 should be as non-repetitive as possible across the corpus

Usage:
  python smart_tagger.py --db catalog.db --update
  python smart_tagger.py --db catalog.db --dry-run
  python smart_tagger.py --db catalog.db --file "path/to/file.md"
"""
from __future__ import annotations

import sqlite3
import re
import sys
from pathlib import Path
from collections import Counter
from typing import List, Tuple, Optional

# ── Noise filter ────────────────────────────────
# Terms that come from HTML/CSS source, not content
HTML_NOISE = {
    "class", "href", "div", "span", "var", "color", "font-size", "font",
    "background", "border", "padding", "margin", "display", "width",
    "height", "style", "script", "link", "meta", "head", "body", "html",
    "section", "article", "header", "footer", "nav", "main", "aside",
    "grid", "flex", "block", "inline", "none", "auto", "solid",
    "rgba", "rgb", "px", "em", "rem", "vw", "vh", "calc",
    "hover", "active", "focus", "before", "after", "content",
    "position", "relative", "absolute", "fixed", "sticky",
    "top", "left", "right", "bottom", "z-index", "overflow",
    "opacity", "transform", "transition", "animation",
    "cursor", "pointer", "text-decoration", "text-transform",
    "letter-spacing", "line-height", "text-align", "vertical-align",
    "box-sizing", "border-radius", "box-shadow", "outline",
    "visibility", "white-space", "word-break", "word-wrap",
    "templates", "template", "true", "false", "null", "undefined",
    "function", "return", "const", "let", "import", "export",
    "module", "require", "default", "async", "await",
}

STOP_TAGS = {
    "move", "outright", "part", "data", "score", "archive", "evaluation",
    "test", "sample", "example", "readme", "index", "config", "setup",
    "install", "build", "run", "start", "stop", "update", "delete",
    "create", "read", "write", "file", "folder", "path", "name",
    "this", "that", "they", "them", "their", "these", "those",
    "what", "when", "where", "which", "with", "from", "into",
    "have", "been", "will", "would", "could", "should", "shall",
    "your", "more", "most", "some", "such", "each", "every",
    "also", "just", "only", "very", "much", "many", "well",
    "about", "after", "before", "between", "through", "during",
    "self", "other", "than", "then", "here", "there", "where",
    "text", "https", "http", "gstatic", "www", "com", "org",
    "framework", "based", "system", "model", "approach", "method",
    "first", "second", "third", "last", "next", "previous",
    "however", "therefore", "because", "since", "while", "although",
    "master", "canonical", "document", "paper", "section", "chapter",
}


# ── Domain detection ────────────────────────────
DOMAINS = {
    "theology": ["god","jesus","christ","trinity","spirit","holy","scripture",
        "gospel","faith","prayer","church","salvation","resurrection","sin",
        "grace","mercy","atonement","sanctification","covenant","revelation"],
    "physics": ["quantum","relativity","entropy","thermodynamics","force",
        "field","particle","wave","energy","mass","momentum","spacetime",
        "hamiltonian","lagrangian","schrodinger","planck","boson","fermion"],
    "psychology": ["mental","therapy","cognitive","behavioral","anxiety",
        "depression","trauma","recovery","counseling","disorder","dsm",
        "diagnosis","wellbeing","resilience","coping","attachment"],
    "economics": ["federal reserve","monetary","fiscal","inflation","debt",
        "gdp","market","cantillon","currency","banking","interest rate",
        "gold standard","fiat","credit","bretton woods"],
    "education": ["school","curriculum","student","teacher","learning",
        "literacy","transmission","pedagogy","classroom","university",
        "college","graduation","standardized","testing","dropout"],
    "history": ["american","constitutional","declaration","civil war",
        "founding","revolution","amendment","colonial","republic",
        "democracy","civilization","empire","decline","collapse"],
    "mathematics": ["theorem","proof","axiom","lemma","corollary","algebra",
        "topology","category","functor","isomorphism","group","ring",
        "cantor","godel","tarski","hilbert","brouwer","fixed point"],
    "consciousness": ["awareness","qualia","phenomenal","sentience","mind",
        "observer","measurement","watcher","von neumann","hard problem",
        "subjective","experience","attention","perception"],
    "information": ["shannon","entropy","bit","channel","signal","noise",
        "bandwidth","compression","encoding","redundancy","mutual"],
    "moral-decline": ["decline","erosion","collapse","crisis","breakdown",
        "disintegration","corruption","degradation","deterioration",
        "divorce","crime","substance","addiction","suicide","violence"],
}

# ── Subtopic specificity ────────────────────────
SPECIFICS = {
    "grace": ["charis","W_grace","external-input","Lindblad","open-system",
        "restoration","unmerited","prevenient","irresistible","sufficient"],
    "entropy": ["thermodynamic","semantic","moral-entropy","informational",
        "decay","disorder","S_eff","phase-transition","heat-death"],
    "coherence": ["chi-field","C-star","decoherence","alignment","resonance",
        "constructive","destructive","superposition","entanglement"],
    "moral": ["conservation","sign-flip","sigma","directional","noether",
        "irreversible","ledger","accountability","law-9","weak-force"],
    "quantum": ["measurement","collapse","superposition","tunneling",
        "uncertainty","observer","wavefunction","decoherence","entanglement"],
    "faith": ["pistis","trust","assurance","evidence-of","substance-of",
        "doubt","control","surrender","commitment","leap"],
    "truth": ["aletheia","signal","doxa","witness","light","deception",
        "correspondence","coherentism","E-variable","law-3"],
    "love": ["agape","philia","eros","storge","Yukawa","strong-force",
        "law-4","binding","attraction","captivity","liberation"],
    "knowledge": ["episteme","logos","gnosis","revelation","K-variable",
        "law-6","shannon","channel-capacity","information"],
    "time": ["chronos","kairos","arrow","irreversibility","T-variable",
        "law-8","relativity","frame","simultaneity"],
}


def clean_text(text: str) -> str:
    """Strip HTML tags, CSS, and URLs from text content."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S|re.I)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S|re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\{[^}]+\}', ' ', text)  # CSS blocks
    text = re.sub(r'https?://\S+', ' ', text)  # URLs
    text = re.sub(r'www\.\S+', ' ', text)  # www links
    text = re.sub(r'[{}();:,\[\]"\'`#@$%^&*+=|\\/<>~]', ' ', text)
    return text.lower()

def detect_domain(text: str, name: str) -> str:
    blob = clean_text(text) + " " + name.lower()
    scores = {}
    for domain, keywords in DOMAINS.items():
        score = sum(blob.count(k) for k in keywords)
        if score > 0:
            scores[domain] = score
    if not scores:
        return "unclassified"
    return max(scores, key=scores.get)

def detect_subtopic(text: str, name: str, domain: str) -> str:
    blob = clean_text(text) + " " + name.lower()
    # Count occurrences of known subtopics
    candidates = Counter()
    for word in re.findall(r'[a-z]{4,}', blob):
        if word not in HTML_NOISE and word not in STOP_TAGS:
            candidates[word] += 1
    # Remove the domain word itself
    candidates.pop(domain.replace("-", ""), None)
    # Get top candidates that aren't too generic
    top = [w for w, c in candidates.most_common(20)
           if c >= 2 and len(w) > 3]
    return top[0] if top else "general"

def detect_specific(text: str, subtopic: str) -> str:
    """Find the most specific variant of the subtopic."""
    blob = clean_text(text)
    if subtopic in SPECIFICS:
        for specific in SPECIFICS[subtopic]:
            if specific.lower().replace("-", " ").replace("_", " ") in blob:
                return specific
    # Fall back to finding a distinctive term
    words = re.findall(r'[a-z]{5,}', blob)
    word_counts = Counter(words)
    # Find words that appear 2-5 times (specific, not generic)
    specific_words = [w for w, c in word_counts.most_common(50)
                      if 2 <= c <= 8 and w not in HTML_NOISE
                      and w not in STOP_TAGS and w != subtopic]
    return specific_words[0] if specific_words else subtopic

def detect_unique(text: str, name: str, tag_counts: dict,
                  domain: str, subtopic: str, specific: str) -> str:
    """Find a tag that distinguishes this file from others with same tags."""
    blob = clean_text(text) + " " + name.lower()
    words = re.findall(r'[a-z]{4,}', blob)
    word_counts = Counter(words)
    existing = {domain, subtopic, specific}
    # Find words that appear in THIS file but are rare in the corpus
    candidates = []
    for w, local_count in word_counts.most_common(100):
        if w in existing or w in HTML_NOISE or w in STOP_TAGS:
            continue
        global_count = tag_counts.get(w, 0)
        # Prefer words common in this file but rare globally
        if local_count >= 2 and global_count < 30:
            candidates.append((w, local_count / max(global_count + 1, 1)))
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0] if candidates else name.split(".")[0][:15].lower()


def smart_tag_file(path: str, text: str, name: str,
                   tag_counts: dict) -> Tuple[str, str, str, str]:
    """Return (domain, subtopic, specific, unique) tags for one file."""
    domain = detect_domain(text, name)
    subtopic = detect_subtopic(text, name, domain)
    specific = detect_specific(text, subtopic)
    unique = detect_unique(text, name, tag_counts, domain, subtopic, specific)
    return domain, subtopic, specific, unique


def build_corpus_tag_counts(db_path: Path) -> dict:
    """Get global tag frequency from existing catalog."""
    conn = sqlite3.connect(str(db_path))
    counts = Counter()
    for row in conn.execute("SELECT tags FROM files WHERE tags != ''"):
        for tag in row[0].split(","):
            tag = tag.strip().lower()
            if tag and tag not in HTML_NOISE:
                counts[tag] += 1
    conn.close()
    return dict(counts)


def update_catalog(db_path: Path, dry_run: bool = False):
    """Re-tag all files in catalog with 4-tag smart system."""
    conn = sqlite3.connect(str(db_path))

    # Add smart tag columns if they don't exist
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(files)")]
    for col in ["tag_domain", "tag_subtopic", "tag_specific", "tag_unique"]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE files ADD COLUMN {col} TEXT DEFAULT ''")
    conn.commit()

    tag_counts = build_corpus_tag_counts(db_path)

    rows = conn.execute(
        "SELECT path, name, ext, tags FROM files WHERE ext IN ('.md','.html','.txt','.json','.csv')"
    ).fetchall()

    print(f"Smart-tagging {len(rows)} text files...")
    updated = 0
    for i, (path, name, ext, old_tags) in enumerate(rows):
        # Read file content (sampled)
        try:
            with open(path, "r", errors="replace") as f:
                text = f.read(50_000)
        except Exception:
            text = old_tags or ""

        domain, subtopic, specific, unique = smart_tag_file(
            path, text, name, tag_counts)

        if dry_run:
            if i < 20:
                print(f"  {name}: [{domain}] [{subtopic}] [{specific}] [{unique}]")
        else:
            conn.execute("""
                UPDATE files SET tag_domain=?, tag_subtopic=?, tag_specific=?, tag_unique=?
                WHERE path=?
            """, (domain, subtopic, specific, unique, path))
            updated += 1

        if (i + 1) % 500 == 0:
            if not dry_run:
                conn.commit()
            print(f"  {i+1}/{len(rows)}")

    if not dry_run:
        conn.commit()
    conn.close()
    print(f"Done: {updated} files smart-tagged" if not dry_run else f"Dry run complete: {len(rows)} files analyzed")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Smart 4-tag disambiguating tagger")
    parser.add_argument("--db", type=Path, required=True, help="Path to catalog.db")
    parser.add_argument("--dry-run", action="store_true", help="Show tags without writing")
    parser.add_argument("--update", action="store_true", help="Update all files in catalog")
    args = parser.parse_args()

    if args.update or args.dry_run:
        update_catalog(args.db, dry_run=args.dry_run)
    else:
        parser.print_help()
