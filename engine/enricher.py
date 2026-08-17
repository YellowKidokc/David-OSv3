"""
enricher.py — low-confidence enrichment (TF-IDF + WordNet pre-pass).

Spliced from FIS/fis_enricher.py and wired to filetagger/wordnet_expander.py.

When a file's confidence < LOW_CONF_THRESHOLD, we don't blind-queue it. We:
  1. expand the filename's words via WordNet (synonyms + parents)   <- pre-pass
  2. TF-IDF char-ngram match it against similar ALREADY-classified files
  3. borrow domain + tags from the closest matches

Corpus, in priority order:
  - filebrain approved rows (best: they carry real DOMAIN__CT__tag codes)
  - the 819k-row reference catalog chi_catalog_v2.db (fallback: name + domain +
    keywords, from which we re-derive tag codes)

Outcomes (same thresholds as fis_enricher):
  enriched  sim >= 0.60  -> domain/tags replaced, re-queued with context
  compare   sim >= 0.30  -> kept, comparison context attached
  uncertain sim <  0.30  -> queued plain, flagged for manual review

Degrades cleanly: if sklearn is missing, enrichment is skipped (no crash).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional, List

import config
import tagger
import wordnet_expander

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False

LOW_CONF_THRESHOLD = 0.50
ENRICH_THRESHOLD   = 0.60
COMPARE_THRESHOLD  = 0.30
TOP_N              = 6
MIN_CORPUS         = 5
REF_SAMPLE         = 300

_SPLIT = re.compile(r"[\s_\-\.]+")

# reference catalog domain_primary (lowercase labels) -> our 2-letter codes
_REF_DOMAIN = {
    "physics": "PH", "theology": "TH", "formal_math": "MT", "history": "GN",
    "epistemology": "EP", "information": "IF", "morality": "MR",
    "sociology": "GN", "consciousness": "CS", "psychology": "CS",
    "ai_methodology": "AI", "information_theory": "IF",
}


def _name_words(name: str) -> List[str]:
    stem = Path(name).stem
    return [w.lower() for w in _SPLIT.split(stem) if len(w) > 1]


def _name_to_text(name: str, expand: bool = False) -> str:
    words = _name_words(name)
    if expand:
        words = wordnet_expander.expand_term_list(words, max_total=20)
    return " ".join(words) if words else Path(name).stem.lower()


def _map_ref_domain(s: str) -> str:
    s = (s or "").strip().lower()
    if s in _REF_DOMAIN:
        return _REF_DOMAIN[s]
    if s.upper() in config.DOMAIN_LABELS:
        return s.upper()
    return "GN"


class _Corpus:
    __slots__ = ("items", "vec", "matrix")

    def __init__(self, items, vec, matrix):
        self.items = items        # list[{"name","domain","tags"}]
        self.vec = vec
        self.matrix = matrix


class Enricher:
    """One per scan. Holds the reference connection + per-extension corpus cache."""

    def __init__(self, con: sqlite3.Connection, reference_db: Optional[str] = None):
        self.con = con
        self.ref: Optional[sqlite3.Connection] = None
        if reference_db and Path(reference_db).exists():
            try:
                self.ref = sqlite3.connect(f"file:{reference_db}?mode=ro", uri=True)
                self.ref.row_factory = sqlite3.Row
            except Exception:
                self.ref = None
        self._cache: dict = {}

    def close(self):
        if self.ref:
            try:
                self.ref.close()
            except Exception:
                pass

    # -- corpus building --------------------------------------------------- #
    def _approved_items(self, ext: str) -> list:
        rows = self.con.execute(
            "SELECT name, proposed_name FROM files "
            "WHERE approved=1 AND proposed_name IS NOT NULL AND ext=? LIMIT 200",
            (ext,)).fetchall()
        if len(rows) < MIN_CORPUS:
            rows = self.con.execute(
                "SELECT name, proposed_name FROM files "
                "WHERE approved=1 AND proposed_name IS NOT NULL LIMIT 200").fetchall()
        items = []
        for r in rows:
            parts = (r["proposed_name"] or "").split("__")
            domain = parts[0] if parts else "GN"
            tags = [t for t in (parts[2].split("-") if len(parts) > 2 else []) if t and t != "GN"]
            items.append({"name": r["name"], "domain": domain, "tags": tags})
        return items

    def _reference_items(self, ext: str) -> list:
        if not self.ref:
            return []
        try:
            rows = self.ref.execute(
                "SELECT name, domain_primary, keywords FROM files "
                "WHERE ext=? AND name IS NOT NULL ORDER BY chi_confidence DESC LIMIT ?",
                (ext, REF_SAMPLE)).fetchall()
            if len(rows) < MIN_CORPUS:
                rows = self.ref.execute(
                    "SELECT name, domain_primary, keywords FROM files "
                    "WHERE name IS NOT NULL ORDER BY chi_confidence DESC LIMIT ?",
                    (REF_SAMPLE,)).fetchall()
        except Exception:
            return []
        items = []
        for r in rows:
            kw = r["keywords"] or ""
            items.append({
                "name": r["name"],
                "domain": _map_ref_domain(r["domain_primary"]),
                "tags": tagger.extract_tags(f"{r['name']} {kw}"),
            })
        return items

    def _corpus(self, ext: str) -> Optional[_Corpus]:
        if not SKLEARN_OK:
            return None
        if ext in self._cache:
            return self._cache[ext]
        items = self._approved_items(ext)
        if len(items) < MIN_CORPUS:
            items = items + self._reference_items(ext)
        if not items:
            self._cache[ext] = None
            return None
        texts = [_name_to_text(i["name"]) for i in items]
        try:
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
            matrix = vec.fit_transform(texts)
        except Exception:
            self._cache[ext] = None
            return None
        corpus = _Corpus(items, vec, matrix)
        self._cache[ext] = corpus
        return corpus

    # -- enrichment -------------------------------------------------------- #
    def enrich(self, name: str, ext: str) -> dict:
        if not SKLEARN_OK:
            return {"outcome": "disabled", "best_sim": 0.0, "note": "sklearn unavailable"}
        corpus = self._corpus(ext)
        if not corpus:
            return {"outcome": "uncertain", "best_sim": 0.0,
                    "note": "no comparison corpus available yet"}

        qtext = _name_to_text(name, expand=True)         # WordNet pre-pass
        try:
            qv = corpus.vec.transform([qtext])
            sims = cosine_similarity(qv, corpus.matrix)[0]
        except Exception as e:
            return {"outcome": "uncertain", "best_sim": 0.0, "note": str(e)}

        order = np.argsort(sims)[::-1][:TOP_N]
        best_sim = float(sims[order[0]]) if len(order) else 0.0

        domain_votes: dict = {}
        tag_votes: dict = {}
        comparisons = []
        for idx in order:
            s = float(sims[idx])
            if s < 0.05:
                break
            it = corpus.items[idx]
            comparisons.append({"name": it["name"], "domain": it["domain"],
                                "tags": it["tags"], "sim": round(s, 3)})
            domain_votes[it["domain"]] = domain_votes.get(it["domain"], 0.0) + s
            for t in it["tags"]:
                tag_votes[t] = tag_votes.get(t, 0.0) + s

        domain_votes.pop("GN", None)
        suggested_domain = max(domain_votes, key=domain_votes.get) if domain_votes else "GN"
        suggested_tags = sorted(tag_votes, key=tag_votes.get, reverse=True)[:int(config.NAMING.get("max_tags", 3))]

        if best_sim >= ENRICH_THRESHOLD:
            outcome, note = "enriched", f"domain/tags from {len(comparisons)} similar files (sim {best_sim:.2f})"
        elif best_sim >= COMPARE_THRESHOLD:
            outcome, note = "compare", f"suggestions from {len(comparisons)} similar files (sim {best_sim:.2f}) — review"
        else:
            outcome, note = "uncertain", f"no strong match (sim {best_sim:.2f}) — manual review"

        return {"outcome": outcome, "best_sim": round(best_sim, 3),
                "suggested_domain": suggested_domain, "suggested_tags": suggested_tags,
                "comparisons": comparisons, "note": note}

    def maybe_enrich(self, rec: "config.FileRecord") -> Optional[dict]:
        """If rec is low-confidence, enrich and patch it in place. Returns the enrichment."""
        if (rec.confidence or 0.0) >= LOW_CONF_THRESHOLD or not rec.proposed_name:
            return None
        enr = self.enrich(rec.name, rec.extension.lower())
        rec.decision = "queue"            # any enriched/uncertain proposal needs a human look
        if enr["outcome"] == "enriched":
            new_domain = enr["suggested_domain"]
            new_tags = enr["suggested_tags"] or rec.tags
            parts = rec.proposed_name.split("__")
            if len(parts) >= 5:
                if new_domain and new_domain != "GN":
                    parts[0] = new_domain
                    rec.domain = new_domain
                    rec.domain_label = config.DOMAIN_LABELS.get(new_domain, rec.domain_label)
                parts[2] = "-".join(new_tags) if new_tags else "GN"
                rec.proposed_name = "__".join(parts)
                rec.tags = new_tags
            rec.reason = enr["note"]
            rec.notes = f"[enriched] {enr['note']}"
        elif enr["outcome"] == "compare":
            top = enr["comparisons"][0] if enr["comparisons"] else None
            rec.reason = enr["note"]
            rec.notes = f"[compare] like '{top['name']}' ({top['sim']})" if top else f"[compare] {enr['note']}"
        else:
            rec.reason = enr["note"]
            rec.notes = f"[{enr['outcome']}] {enr['note']}"
        return enr
