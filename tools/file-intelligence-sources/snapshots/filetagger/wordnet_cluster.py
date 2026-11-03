#!/usr/bin/env python3
"""Map the full semantic neighborhood of a word through WordNet."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from nltk.corpus import wordnet as wn

def sim(w1, w2):
    s1, s2 = wn.synsets(w1), wn.synsets(w2)
    if not s1 or not s2: return 0.0
    best = 0.0
    for a in s1[:3]:
        for b in s2[:3]:
            try:
                v = a.wup_similarity(b) or 0.0
                if v > best: best = v
            except: pass
    return round(best, 3)

def cluster_map(target, compare_words):
    """Show how a target word relates to a field of other words."""
    pairs = [(sim(target, w), w) for w in compare_words if w != target]
    pairs.sort(reverse=True)
    print(f"\n{'='*60}")
    print(f"  CLUSTER MAP: {target.upper()}")
    print(f"  What is {target} semantically close to?")
    print(f"{'='*60}\n")
    
    # Strength bands
    strong = [(s,w) for s,w in pairs if s >= 0.6]
    moderate = [(s,w) for s,w in pairs if 0.4 <= s < 0.6]
    weak = [(s,w) for s,w in pairs if 0.2 <= s < 0.4]
    distant = [(s,w) for s,w in pairs if s < 0.2]
    
    if strong:
        print(f"  STRONG (>= 0.6) ------")
        for s, w in strong:
            bar = "|" * int(s * 30)
            print(f"    {s:.3f}  {bar}  {w}")
    if moderate:
        print(f"\n  MODERATE (0.4-0.6) ---")
        for s, w in moderate:
            bar = "|" * int(s * 30)
            print(f"    {s:.3f}  {bar}  {w}")
    if weak:
        print(f"\n  WEAK (0.2-0.4) ------")
        for s, w in weak:
            bar = "|" * int(s * 30)
            print(f"    {s:.3f}  {bar}  {w}")
    if distant:
        print(f"\n  DISTANT (< 0.2) -----")
        for s, w in distant:
            bar = "|" * int(s * 30)
            print(f"    {s:.3f}  {bar}  {w}")
    print()

def expand_cluster(word):
    """Show WordNet's internal structure for a word."""
    print(f"\n{'='*60}")
    print(f"  WORDNET INTERNAL: {word.upper()}")
    print(f"  What does the language think {word} IS?")
    print(f"{'='*60}\n")
    for ss in wn.synsets(word):
        print(f"  Sense: {ss.name()}")
        print(f"    Definition: {ss.definition()}")
        syns = [l.name().replace('_',' ') for l in ss.lemmas()]
        print(f"    Synonyms: {', '.join(syns)}")
        for h in ss.hypernyms():
            print(f"    IS-A: {h.name()} ({h.definition()})")
        for hypo in ss.hyponyms()[:5]:
            print(f"    TYPE-OF: {hypo.name()} ({hypo.definition()})")
        print()

# ── THE BIG WORD FIELD ──
all_words = [
    # Theological
    "justice","mercy","grace","love","faith","truth","holiness",
    "salvation","redemption","atonement","forgiveness","sin",
    "judgment","punishment","sacrifice","restoration","reconciliation",
    "repentance","sanctification","righteousness",
    # Moral
    "accountability","responsibility","repair","compassion","dignity",
    "kindness","patience","gentleness","goodness","faithfulness",
    "joy","peace","hope","humility","courage",
    # Anti
    "hatred","contempt","cruelty","corruption","betrayal","domination",
    "coercion","manipulation","despair","anxiety","rage","vengeance",
    # Structural
    "coherence","entropy","order","chaos","unity","harmony",
    "decay","collapse","balance","equilibrium",
    # Cost
    "cost","debt","payment","burden","price","penalty",
    "restitution","compensation","substitute","mediator",
]

# Map mercy's neighborhood
print("\n" + "#"*60)
print("  MERCY DEEP ANALYSIS")
print("#"*60)

cluster_map("mercy", all_words)
expand_cluster("mercy")

# Now do the same for sacrifice (the hub)
cluster_map("sacrifice", all_words)

# And justice for comparison
cluster_map("justice", all_words)

# And coherence
cluster_map("coherence", all_words)
