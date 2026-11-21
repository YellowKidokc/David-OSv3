"""attention_vector.py — Extract the 20-30 words a reader would clue into for each document.

Not a keyword list. An attention fingerprint: the words that carry the most discriminative
information for THIS document given the full corpus. Two layers:

  Layer 1: TF-IDF — words that appear often here but rarely elsewhere
  Layer 2: Law-group collapsing — synonyms within a law family merge into one signal,
           scored by the combined weight. "justice" + "mercy" + "free energy" = one L5 signal.

Output per document: a vector of (term, weight) pairs sorted by attention weight.
Output per corpus: a similarity matrix showing which papers share attention patterns.

Usage:
    from attention_vector import AttentionEngine
    engine = AttentionEngine(lexicon_path="lexicon_canonical.json")
    engine.ingest(cards, text_cache)       # build the corpus model
    vec = engine.vector(card.path)         # get one document's attention vector
    sim = engine.similarity(path_a, path_b)
    neighbors = engine.nearest(card.path, k=5)
    engine.export(output_dir)              # write vectors + similarity matrix
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

STOPWORDS = set("""the and for that this with from are was were been have has had not but you your our their
they them his her its which what when where who will would can could should into about than then there these
those also more most such only other some any all one two each over under very just like make made does did
being been here how why our out use used using upon via per may might must shall also even still just well
much many now new get got its own way back well also really very much well between after before through
both during another only some them then than been each more most other such these those when where while
said would could should since however because although before during after while within without between
among through along another either both several many some another such every each either neither whether
whether both just even still already also quite rather than more less most least very much many few little
several both either neither another other such every each whether just even still already also quite""".split())

# Extra stop words for academic/theophysics documents — common but not discriminative
DOMAIN_STOPS = set("""paper document section chapter part note draft introduction conclusion references
abstract figure table equation proof theorem lemma corollary appendix analysis result discussion
method approach framework model system structure theory claim argument evidence support demonstrate
show prove establish describe present propose suggest consider examine explore investigate study
review discuss analyze compare contrast evaluate assess determine identify define explain interpret
page pages read file folder version author date title status series position type kind format""".split())

ALL_STOPS = STOPWORDS | DOMAIN_STOPS


@dataclass
class AttentionVector:
    path: str
    terms: list[tuple[str, float]]           # (term, weight) sorted by weight desc
    law_signals: dict[str, float] = field(default_factory=dict)  # law -> combined weight
    top_law: str = ""
    vector_norm: float = 0.0


class AttentionEngine:
    def __init__(self, lexicon_path: str | Path | None = None):
        self.doc_freqs: Counter = Counter()   # term -> how many docs contain it
        self.doc_terms: dict[str, Counter] = {}  # path -> term counts
        self.n_docs: int = 0
        self.vectors: dict[str, AttentionVector] = {}

        # Law groups from lexicon
        self.law_groups: dict[str, set[str]] = {}     # law_name -> terms
        self.term_to_law: dict[str, str] = {}          # term -> law_name
        if lexicon_path and Path(lexicon_path).exists():
            data = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
            for law, terms in data.get("LAW_KEYWORDS", {}).items():
                lset = set(t.lower() for t in terms)
                self.law_groups[law] = lset
                for t in lset:
                    self.term_to_law[t] = law
            # Add fruits/anti-fruits to L4 (Strong Force / Love)
            for sheet in ["FRUITS", "ANTI_FRUITS"]:
                for t in data.get(sheet, []):
                    tl = t.lower()
                    self.law_groups.setdefault("L4_StrongForce", set()).add(tl)
                    self.term_to_law.setdefault(tl, "L4_StrongForce")
            # Coherence terms to L10
            for t in data.get("COHERENCE_TERMS", []):
                tl = t.lower()
                self.law_groups.setdefault("L10_Coherence", set()).add(tl)
                self.term_to_law.setdefault(tl, "L10_Coherence")

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in ALL_STOPS]

    def ingest(self, paths_and_texts: dict[str, str]):
        """Build the corpus model from {path: text_content}."""
        self.doc_terms.clear()
        self.doc_freqs.clear()
        self.vectors.clear()

        for path, text in paths_and_texts.items():
            tokens = self._tokenize(text)
            if len(tokens) < 5:
                continue
            counts = Counter(tokens)
            self.doc_terms[path] = counts
            for term in counts:
                self.doc_freqs[term] += 1

        self.n_docs = len(self.doc_terms)
        if self.n_docs == 0:
            return

        # Build attention vectors
        for path, counts in self.doc_terms.items():
            self.vectors[path] = self._build_vector(path, counts)

    def _build_vector(self, path: str, counts: Counter, top_n: int = 30) -> AttentionVector:
        total_terms = sum(counts.values())
        scored = []
        for term, count in counts.items():
            tf = count / total_terms
            df = self.doc_freqs.get(term, 1)
            idf = math.log((self.n_docs + 1) / (df + 1)) + 1
            scored.append((term, round(tf * idf, 6)))

        scored.sort(key=lambda x: -x[1])
        top = scored[:top_n]

        # Layer 2: law-group collapsing — combine weights per law
        law_signals: dict[str, float] = defaultdict(float)
        for term, weight in top:
            law = self.term_to_law.get(term)
            if law:
                law_signals[law] += weight
        law_signals = dict(sorted(law_signals.items(), key=lambda x: -x[1]))
        top_law = next(iter(law_signals), "")

        norm = math.sqrt(sum(w * w for _, w in top))

        return AttentionVector(
            path=path,
            terms=top,
            law_signals=law_signals,
            top_law=top_law,
            vector_norm=round(norm, 6),
        )

    def vector(self, path: str) -> Optional[AttentionVector]:
        return self.vectors.get(path)

    def similarity(self, path_a: str, path_b: str) -> float:
        """Cosine similarity between two attention vectors."""
        va = self.vectors.get(path_a)
        vb = self.vectors.get(path_b)
        if not va or not vb or va.vector_norm == 0 or vb.vector_norm == 0:
            return 0.0
        da = dict(va.terms)
        db = dict(vb.terms)
        dot = sum(da[t] * db[t] for t in da if t in db)
        return round(dot / (va.vector_norm * vb.vector_norm), 4)

    def nearest(self, path: str, k: int = 5) -> list[tuple[str, float]]:
        """Find the k most similar documents to the given path."""
        if path not in self.vectors:
            return []
        sims = [(p, self.similarity(path, p)) for p in self.vectors if p != path]
        sims.sort(key=lambda x: -x[1])
        return sims[:k]

    def cluster_by_law(self) -> dict[str, list[tuple[str, float]]]:
        """Group documents by their dominant law signal."""
        by_law: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for path, vec in self.vectors.items():
            if vec.top_law:
                by_law[vec.top_law].append((path, vec.law_signals[vec.top_law]))
        for law in by_law:
            by_law[law].sort(key=lambda x: -x[1])
        return dict(by_law)

    def export(self, output_dir: Path):
        """Write attention vectors and summary."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Per-document vectors
        vecs = {}
        for path, vec in sorted(self.vectors.items()):
            vecs[path] = {
                "terms": vec.terms,
                "law_signals": vec.law_signals,
                "top_law": vec.top_law,
                "norm": vec.vector_norm,
            }
        (output_dir / "attention_vectors.json").write_text(
            json.dumps(vecs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Corpus summary
        law_clusters = self.cluster_by_law()
        summary = {
            "n_docs": self.n_docs,
            "n_unique_terms": len(self.doc_freqs),
            "law_cluster_sizes": {law: len(docs) for law, docs in sorted(law_clusters.items())},
            "most_discriminative_terms": self.doc_freqs.most_common()[-30:],  # rarest terms
            "most_common_terms": self.doc_freqs.most_common(30),
        }
        (output_dir / "attention_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        print(f"Attention vectors written for {self.n_docs} documents")
        print(f"  Unique terms: {len(self.doc_freqs)}")
        for law, docs in sorted(law_clusters.items(), key=lambda x: -len(x[1])):
            print(f"  {law}: {len(docs)} docs")
