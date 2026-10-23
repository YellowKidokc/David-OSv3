"""Reverse fingerprint — learn what a set of example documents has in common,
then score any other document by how similar it is (0-100%).

Pure Python TF-IDF. No external deps.

  fp = learn(example_texts, background_texts, name="axioms")
  fp["traits"]            -> [(term, weight, share_of_examples), ...]  "how they're similar"
  similarity(fp, text)    -> 0..100   (100 ≈ as close as a typical example is)
  save(fp, path) / load(path)
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from statistics import median

STOP = set("""
a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having
he her here hers him his how i if in into is it its itself just me more most my no nor not now of off on
once only or other our ours out over own same she should so some such than that the their theirs them then
there these they this those through to too under until up very was we were what when where which while who
whom why will with would you your yours http https www com html div span class style nbsp amp quot
""".split())

TOP_TERMS = 400


def tokens(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-zα-ωχψφ][a-z0-9α-ωχψφ_'-]{2,}", text.lower()) if w not in STOP]
    return words + [f"{a} {b}" for a, b in zip(words, words[1:])]


def _tf(text: str) -> Counter:
    return Counter(tokens(text))


def _vec(tf: Counter, idf: dict[str, float], keep=None) -> dict[str, float]:
    total = sum(tf.values()) or 1
    v = {t: (c / total) * idf.get(t, 0.0) for t, c in tf.items() if keep is None or t in keep}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norm for t, x in v.items() if x}


def _cos(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def learn(examples: list[str], background: list[str], name: str = "fingerprint") -> dict:
    ex_tfs = [_tf(t) for t in examples if t.strip()]
    bg_tfs = [_tf(t) for t in background if t.strip()]
    if len(ex_tfs) < 2:
        raise ValueError("Need at least 2 readable example documents.")
    corpus = ex_tfs + bg_tfs
    n = len(corpus)
    df = Counter()
    for tf in corpus:
        df.update(tf.keys())
    idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}

    ex_df = Counter()
    for tf in ex_tfs:
        ex_df.update(tf.keys())

    # centroid of example vectors; ignore terms that appear in only one example
    centroid = Counter()
    for tf in ex_tfs:
        for t, x in _vec(tf, idf).items():
            if ex_df[t] >= 2:
                centroid[t] += x / len(ex_tfs)
    top = dict(centroid.most_common(TOP_TERMS))
    norm = math.sqrt(sum(x * x for x in top.values())) or 1.0
    top = {t: x / norm for t, x in top.items()}

    fp = {
        "name": name,
        "created": datetime.now().isoformat(timespec="seconds"),
        "n_examples": len(ex_tfs),
        "idf": {t: idf[t] for t in top},
        "centroid": top,
        "traits": [(t, round(w, 4), round(ex_df[t] / len(ex_tfs), 2)) for t, w in list(top.items())[:40]],
    }
    # calibrate: typical example-to-centroid cosine = 100%
    self_scores = [_cos(_vec(tf, fp["idf"], top), top) for tf in ex_tfs]
    fp["calibration"] = median(self_scores) or 1e-9
    return fp


def similarity(fp: dict, text: str) -> int:
    if not text.strip():
        return 0
    v = _vec(_tf(text), fp["idf"], fp["centroid"])
    return int(min(100, round(100 * _cos(v, fp["centroid"]) / fp["calibration"])))


def shared_traits(fp: dict, text: str, k: int = 8) -> list[str]:
    tf = _tf(text)
    return [t for t, _, _ in fp["traits"] if t in tf][:k]


def save(fp: dict, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fp, f, ensure_ascii=False, indent=1)


def load(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
