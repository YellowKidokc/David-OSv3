#!/usr/bin/env python3
"""
WordNet Profile Expander — auto-expand chi_profiles term lists.
===============================================================
Takes 5-10 seed words per category, uses WordNet to generate
50-80 related terms. Same profiles, richer vocabulary, zero API calls.

Usage:
  python wordnet_expander.py --profile negotiation --show
  python wordnet_expander.py --profile all --export expanded_profiles.json
  python wordnet_expander.py --seed "justice,mercy,grace" --expand
"""
import json, argparse, sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Set, Tuple

try:
    from nltk.corpus import wordnet as wn
    _HAS_WN = True
except ImportError:
    _HAS_WN = False
    print("Install nltk: pip install nltk && python -c \"import nltk; nltk.download('wordnet')\"")

# ── Expansion Functions ──
def get_synonyms(word: str) -> Set[str]:
    """Get all synonyms from all synsets of a word."""
    syns = set()
    for ss in wn.synsets(word):
        for lemma in ss.lemmas():
            name = lemma.name().replace("_", " ").lower()
            if name != word.lower() and len(name) > 2:
                syns.add(name)
    return syns

def get_hypernyms(word: str, depth: int = 2) -> Set[str]:
    """Get parent concepts (more general terms)."""
    terms = set()
    for ss in wn.synsets(word):
        for hyp in ss.hypernyms():
            for lemma in hyp.lemmas():
                terms.add(lemma.name().replace("_", " ").lower())
            if depth > 1:
                for hyp2 in hyp.hypernyms():
                    for lemma in hyp2.lemmas():
                        terms.add(lemma.name().replace("_", " ").lower())
    return terms

def get_hyponyms(word: str) -> Set[str]:
    """Get child concepts (more specific terms)."""
    terms = set()
    for ss in wn.synsets(word):
        for hypo in ss.hyponyms():
            for lemma in hypo.lemmas():
                terms.add(lemma.name().replace("_", " ").lower())
    return terms

def get_related(word: str) -> Set[str]:
    """Get derivationally related forms."""
    terms = set()
    for ss in wn.synsets(word):
        for lemma in ss.lemmas():
            for rel in lemma.derivationally_related_forms():
                terms.add(rel.name().replace("_", " ").lower())
    return terms

def similarity_score(word1: str, word2: str) -> float:
    """Wu-Palmer similarity between two words (0-1)."""
    s1 = wn.synsets(word1)
    s2 = wn.synsets(word2)
    if not s1 or not s2:
        return 0.0
    try:
        return s1[0].wup_similarity(s2[0]) or 0.0
    except Exception:
        return 0.0

def expand_term(word: str, max_per_source: int = 8) -> Dict[str, Set[str]]:
    """Expand one word through all WordNet relations."""
    return {
        "synonyms": set(list(get_synonyms(word))[:max_per_source]),
        "hypernyms": set(list(get_hypernyms(word))[:max_per_source]),
        "hyponyms": set(list(get_hyponyms(word))[:max_per_source]),
        "related": set(list(get_related(word))[:max_per_source]),
    }

def expand_term_list(seeds: List[str], max_total: int = 80) -> List[str]:
    """Expand a list of seed terms into a richer vocabulary."""
    all_terms = set(s.lower() for s in seeds)
    for seed in seeds:
        expansions = expand_term(seed.lower())
        for source, terms in expansions.items():
            all_terms.update(terms)
    # Sort by length (shorter = more common = more useful)
    result = sorted(all_terms, key=lambda t: (len(t), t))
    return result[:max_total]

# ── Profile Expansion ──
def expand_profile(profile: Dict, max_per_category: int = 80) -> Dict:
    """Expand all term lists in a profile using WordNet."""
    expanded = dict(profile)  # copy
    categories = ["justice", "mercy", "cost_bearer", "coercion",
                  "evidence", "overclaim", "positive", "negative"]
    for cat in categories:
        if cat in profile and isinstance(profile[cat], list):
            seeds = profile[cat]
            expanded_terms = expand_term_list(seeds, max_per_category)
            expanded[cat] = expanded_terms
            expanded[f"{cat}_seeds"] = seeds  # keep originals
            expanded[f"{cat}_count"] = f"{len(seeds)} seeds -> {len(expanded_terms)} terms"
    return expanded

def show_expansion(word: str):
    """Show what WordNet knows about a word."""
    print(f"\n{'='*50}")
    print(f"  WORDNET EXPANSION: {word}")
    print(f"{'='*50}")
    for ss in wn.synsets(word)[:4]:
        print(f"\n  {ss.name()}: {ss.definition()}")
        syns = [l.name().replace("_", " ") for l in ss.lemmas()]
        print(f"    Synonyms: {', '.join(syns)}")
    exps = expand_term(word)
    for source, terms in exps.items():
        if terms:
            print(f"\n  {source}: {', '.join(sorted(terms)[:10])}")
    print(f"{'='*50}\n")

def compare_words(words: List[str]):
    """Show similarity matrix between words."""
    print(f"\n  SIMILARITY MATRIX:")
    print(f"  {'':12s}", end="")
    for w in words:
        print(f"  {w[:8]:>8s}", end="")
    print()
    for w1 in words:
        print(f"  {w1[:12]:12s}", end="")
        for w2 in words:
            sim = similarity_score(w1, w2)
            print(f"  {sim:8.3f}", end="")
        print()
    print()

# ── CLI ──
def main():
    ap = argparse.ArgumentParser(description="WordNet Profile Expander")
    ap.add_argument("--expand", "-e", help="Expand a single word")
    ap.add_argument("--seed", "-s", help="Comma-separated seed words to expand")
    ap.add_argument("--compare", "-c", help="Comma-separated words to compare similarity")
    ap.add_argument("--profile", "-p", help="Expand a chi_profiles profile by name")
    ap.add_argument("--export", help="Export expanded profiles to JSON")
    ap.add_argument("--max", type=int, default=80, help="Max terms per category")
    a = ap.parse_args()

    if not _HAS_WN:
        return 1

    if a.expand:
        show_expansion(a.expand)
        return 0

    if a.compare:
        words = [w.strip() for w in a.compare.split(",")]
        compare_words(words)
        return 0

    if a.seed:
        seeds = [w.strip() for w in a.seed.split(",")]
        expanded = expand_term_list(seeds, a.max)
        print(f"\n  {len(seeds)} seeds -> {len(expanded)} terms:\n")
        for t in expanded:
            is_seed = t in [s.lower() for s in seeds]
            marker = " [SEED]" if is_seed else ""
            print(f"    {t}{marker}")
        return 0

    if a.profile:
        # Import profiles from chi_profiles
        sys.path.insert(0, str(Path(__file__).parent))
        try:
            from chi_profiles import PROFILES
        except ImportError:
            print("chi_profiles.py not found in same directory")
            return 1

        if a.profile == "all":
            names = list(PROFILES.keys())
        else:
            names = [a.profile]

        results = {}
        for name in names:
            if name not in PROFILES:
                print(f"Unknown profile: {name}")
                continue
            print(f"\nExpanding profile: {name}...")
            expanded = expand_profile(PROFILES[name], a.max)
            results[name] = expanded
            # Show summary
            for cat in ["justice","mercy","cost_bearer","coercion","evidence","overclaim","positive","negative"]:
                count_key = f"{cat}_count"
                if count_key in expanded:
                    print(f"  {cat:15s}  {expanded[count_key]}")

        if a.export:
            # Clean for JSON (sets -> lists)
            Path(a.export).write_text(
                json.dumps(results, indent=2, default=list, ensure_ascii=False),
                encoding="utf-8")
            print(f"\nExported: {a.export}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
