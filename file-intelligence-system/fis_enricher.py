"""
fis_enricher.py — Low-confidence enrichment for FIS naming proposals.

When confidence < LOW_CONF_THRESHOLD (default 0.50):
  1. Query DB for already-approved files with same extension or folder class
  2. TF-IDF cosine similarity between the uncertain file's name and approved names
  3. Pull tag/domain patterns from the top-N most similar approved files
  4. If similarity is strong enough, override the uncertain proposal's tags
  5. Return enriched proposal + comparison context for the approval queue UI

Three outcomes:
  ENRICHED   — similarity >= 0.60  → tags replaced, re-queued with context
  COMPARE    — similarity 0.30–0.59 → tags suggested, queued with comparison list
  UNCERTAIN  — similarity < 0.30   → queued plain, flagged for manual review
"""

import logging
import sqlite3
from pathlib import Path

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

LOW_CONF_THRESHOLD  = 0.50   # below this → trigger enricher
ENRICH_THRESHOLD    = 0.60   # similarity above this → override tags
COMPARE_THRESHOLD   = 0.30   # similarity above this → suggest + compare
TOP_N               = 6      # how many similar files to pull


# ---------------------------------------------------------------------------
# Text prep  (filename → bag of words for TF-IDF)
# ---------------------------------------------------------------------------

import re

_SPLIT = re.compile(r"[\s_\-\.]+")

def _name_to_text(name: str) -> str:
    """Turn a filename stem into lowercased space-separated words."""
    stem  = Path(name).stem
    words = [w.lower() for w in _SPLIT.split(stem) if len(w) > 1]
    return " ".join(words) if words else stem.lower()


# ---------------------------------------------------------------------------
# Approved corpus loader  (cached per session)
# ---------------------------------------------------------------------------

_corpus_cache: dict = {}   # db_path → {"names": [...], "rows": [...], "ts": float}

def _load_approved(db_path: str, ext: str, folder_class: str) -> list[dict]:
    """
    Fetch approved files from DB that share the same extension OR folder class.
    Falls back to ALL approved files if the filtered set is too small.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    c = con.cursor()

    rows = c.execute("""
        SELECT name, ext, proposed_name, chi_domain, content_type, folder_class,
               chi_confidence
        FROM files
        WHERE approved = 1
          AND proposed_name IS NOT NULL
          AND (ext = ? OR folder_class = ?)
        ORDER BY chi_confidence DESC
        LIMIT 200
    """, (ext, folder_class)).fetchall()

    if len(rows) < 5:
        # widen: any approved file
        rows = c.execute("""
            SELECT name, ext, proposed_name, chi_domain, content_type, folder_class,
                   chi_confidence
            FROM files
            WHERE approved = 1
              AND proposed_name IS NOT NULL
            ORDER BY chi_confidence DESC
            LIMIT 200
        """).fetchall()

    con.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Core enricher
# ---------------------------------------------------------------------------

def enrich(rec: dict, db_path: str) -> dict:
    """
    Given a low-confidence file record, find similar approved files and
    return an enrichment dict with suggested tags, domain, and comparisons.

    Returns:
    {
        "outcome":      "enriched" | "compare" | "uncertain" | "disabled",
        "best_sim":     0.74,
        "suggested_domain": "TH",
        "suggested_tags":   ["CSN", "COH"],
        "comparisons": [
            {"name": "...", "proposed_name": "TH__COD__CSN-COH__...", "sim": 0.74},
            ...
        ],
        "note": "human-readable explanation"
    }
    """
    if not SKLEARN_OK:
        return {"outcome": "disabled", "note": "sklearn not available"}

    name         = rec.get("name", "")
    ext          = (rec.get("ext") or Path(rec.get("path","")).suffix).lower()
    folder_class = rec.get("folder_class") or "dump"

    corpus = _load_approved(db_path, ext, folder_class)
    if not corpus:
        return {"outcome": "uncertain", "best_sim": 0.0,
                "note": "no approved files to compare against yet"}

    # build TF-IDF over approved filenames + the query filename
    query_text   = _name_to_text(name)
    corpus_texts = [_name_to_text(r["name"]) for r in corpus]
    all_texts    = corpus_texts + [query_text]

    try:
        vec    = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        matrix = vec.fit_transform(all_texts)
        sims   = cosine_similarity(matrix[-1], matrix[:-1])[0]   # query vs corpus
    except Exception as e:
        logging.debug("enricher TF-IDF failed: %s", e)
        return {"outcome": "uncertain", "best_sim": 0.0, "note": str(e)}

    top_idx  = np.argsort(sims)[::-1][:TOP_N]
    top_sims = sims[top_idx]
    best_sim = float(top_sims[0]) if len(top_sims) else 0.0

    # pull comparison details
    comparisons = []
    for i, idx in enumerate(top_idx):
        if top_sims[i] < 0.05:
            break
        r = corpus[idx]
        comparisons.append({
            "name":          r["name"] + r["ext"],
            "proposed_name": r["proposed_name"],
            "domain":        r["chi_domain"],
            "content_type":  r["content_type"],
            "sim":           round(float(top_sims[i]), 3),
        })

    # vote on domain + tags from top matches
    domain_votes: dict[str, float] = {}
    tag_votes:    dict[str, float] = {}

    for comp in comparisons:
        weight = comp["sim"]
        pn = comp["proposed_name"] or ""
        parts = pn.split("__")
        if len(parts) >= 1:
            d = parts[0]
            domain_votes[d] = domain_votes.get(d, 0.0) + weight
        if len(parts) >= 3:
            for t in parts[2].split("-"):
                if t and t != "GN":
                    tag_votes[t] = tag_votes.get(t, 0.0) + weight

    suggested_domain = max(domain_votes, key=domain_votes.get) if domain_votes else "GN"
    suggested_tags   = sorted(tag_votes, key=tag_votes.get, reverse=True)[:3]

    # determine outcome
    if best_sim >= ENRICH_THRESHOLD:
        outcome = "enriched"
        note    = (f"Tags/domain replaced from {len(comparisons)} similar approved files "
                   f"(best similarity {best_sim:.2f})")
    elif best_sim >= COMPARE_THRESHOLD:
        outcome = "compare"
        note    = (f"Tags suggested from {len(comparisons)} similar approved files "
                   f"(best similarity {best_sim:.2f}) — review before approving")
    else:
        outcome = "uncertain"
        note    = (f"No strong match found (best similarity {best_sim:.2f}) "
                   f"— manual review needed")

    return {
        "outcome":          outcome,
        "best_sim":         round(best_sim, 3),
        "suggested_domain": suggested_domain,
        "suggested_tags":   suggested_tags,
        "comparisons":      comparisons,
        "note":             note,
    }


# ---------------------------------------------------------------------------
# Integration helper — called from fis_namer.propose_name()
# ---------------------------------------------------------------------------

def maybe_enrich(result: dict, rec: dict, db_path: str) -> dict:
    """
    If the proposal is below LOW_CONF_THRESHOLD, run enrichment and
    patch the result dict in-place.  Returns the (possibly updated) result.
    """
    conf = rec.get("chi_confidence") or 0.0
    if conf >= LOW_CONF_THRESHOLD:
        return result   # confident enough — no enrichment needed

    enrichment = enrich(rec, db_path)
    result["enrichment"] = enrichment

    outcome = enrichment.get("outcome", "uncertain")

    if outcome == "enriched":
        # override tags and domain with what similar files used
        new_domain = enrichment["suggested_domain"]
        new_tags   = enrichment["suggested_tags"] or result.get("tags", [])
        tag_str    = "-".join(new_tags) if new_tags else "GN"
        ext        = rec.get("ext", "")
        old_parts  = (result.get("proposed_name") or "").split("__")
        ct_code    = old_parts[1] if len(old_parts) > 1 else result.get("ct_code","DOC")
        date_str   = old_parts[3] if len(old_parts) > 3 else result.get("date_str","000000")
        st_code    = (old_parts[4].split(".")[0]
                      if len(old_parts) > 4 else result.get("status_code","AC"))

        result["proposed_name"] = f"{new_domain}__{ct_code}__{tag_str}__{date_str}__{st_code}{ext}"
        result["domain_code"]   = new_domain
        result["tags"]          = new_tags
        result["decision"]      = "queue"   # still needs one human confirm after tag change
        result["reason"]        = enrichment["note"]

    elif outcome == "compare":
        # keep existing proposal but add comparison context
        result["decision"] = "queue"
        result["reason"]   = enrichment["note"]

    else:   # uncertain
        result["decision"] = "queue"
        result["reason"]   = enrichment["note"]

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, json
    db   = sys.argv[1] if len(sys.argv) > 1 else "fis_catalog.db"
    name = sys.argv[2] if len(sys.argv) > 2 else "test_file.py"
    rec  = {"name": name, "ext": Path(name).suffix, "folder_class": "project",
            "chi_confidence": 0.30}
    result = enrich(rec, db)
    print(json.dumps(result, indent=2))
