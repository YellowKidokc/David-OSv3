#!/usr/bin/env python3
"""Deep WordNet analysis of Theophysics framework terms."""
from nltk.corpus import wordnet as wn
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def sim(w1, w2):
    s1, s2 = wn.synsets(w1), wn.synsets(w2)
    if not s1 or not s2: return 0.0
    try: return round(s1[0].wup_similarity(s2[0]) or 0.0, 3)
    except: return 0.0

def matrix(title, words):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    # Header
    print(f"  {'':14s}", end="")
    for w in words:
        print(f"{w[:10]:>10s}", end="")
    print()
    # Rows
    for w1 in words:
        print(f"  {w1[:14]:14s}", end="")
        for w2 in words:
            s = sim(w1, w2)
            marker = " " if w1 == w2 else "*" if s >= 0.6 else "+" if s >= 0.4 else " "
            print(f"    {s:.3f}{marker}", end="")
        print()
    # Find strongest pairs (excluding self)
    pairs = []
    for i, w1 in enumerate(words):
        for j, w2 in enumerate(words):
            if i < j:
                pairs.append((sim(w1, w2), w1, w2))
    pairs.sort(reverse=True)
    print(f"\n  Strongest connections:")
    for s, w1, w2 in pairs[:8]:
        print(f"    {w1:14s} <-> {w2:14s}  {s:.3f}")
    print(f"\n  Weakest connections:")
    for s, w1, w2 in pairs[-5:]:
        print(f"    {w1:14s} <-> {w2:14s}  {s:.3f}")

# 1. FRUITS OF THE SPIRIT
print("\n" + "#"*70)
print("  THEOPHYSICS WORDNET DEEP ANALYSIS")
print("#"*70)

matrix("FRUITS OF THE SPIRIT",
    ["love","joy","peace","patience","kindness",
     "goodness","faithfulness","gentleness","self-control"])

# 2. FRUITS vs ANTI-FRUITS
matrix("FRUIT vs ANTI-FRUIT PAIRS",
    ["love","hatred","joy","despair","peace","anxiety",
     "patience","cruelty","kindness","contempt"])

# 3. LAW SPIRITUAL TERMS
matrix("10 LAWS - SPIRITUAL AXIS",
    ["grace","will","truth","love","justice",
     "faith","mercy","coherence","salvation","holiness"])

# 4. CROSS-DOMAIN BRIDGES
matrix("PHYSICS <-> THEOLOGY BRIDGES",
    ["gravity","grace","entropy","judgment",
     "coherence","unity","force","power",
     "light","truth","decay","corruption"])

# 5. MASTER EQUATION VARIABLES (spiritual names)
matrix("MASTER EQUATION SPIRITUAL NAMES",
    ["grace","alignment","truth","entropy","time",
     "knowledge","love","faith","force","coherence"])

# 6. THE CORE CLUSTER: justice/mercy/cost
matrix("JUSTICE-MERCY-COST CLUSTER",
    ["justice","mercy","grace","sacrifice","atonement",
     "forgiveness","restoration","judgment","punishment",
     "redemption","reconciliation","repair"])
