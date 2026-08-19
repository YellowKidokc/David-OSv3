"""
FIS vector space - shared coordinate derivation for the corpus visualisers.

Both the 3D cluster map (fis_visualizer.py) and the Master Equation graph
(fis_meq_graph.py) place files in the same space, so the placement rules live
here once rather than drifting apart in two files.

The three axes:

    X  domain      theology (-1)  <->  physics (+1),  bridge material near 0
    Y  document    narrative (-1) <->  formal/axiomatic (+1)
    Z  coherence   0 -> 1, how strongly the master-equation signal is present

Nothing here re-reads the corpus. Every value is derived from what the scan
already recorded in fis_folder_memory.sqlite.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_DEFAULT = Path(__file__).with_name("fis_folder_memory.sqlite")

# ---------------------------------------------------------------------------
# X axis: where the file sits between theology and physics
# ---------------------------------------------------------------------------
# CHI factors carry a native lean. G is gravity AND grace, so it sits at 0 -
# that duality is the framework's claim, not a scoring problem to solve.
CHI_DOMAIN_LEAN = {
    "G":  0.0,   # gravity / grace - dual by construction
    "M": -0.3,   # moral alignment / momentum
    "E":  0.2,   # truth signal / electromagnetism
    "S":  0.7,   # entropy / thermodynamics
    "T":  0.6,   # time / relativity
    "K":  0.3,   # knowledge / Shannon information
    "R":  0.0,   # relational frame / Lorentz frame - dual
    "Q":  0.7,   # quantum
    "F": -0.6,   # faith / fruit
    "C": -0.5,   # Christ alignment / coherence
}

# The recorded top domain is a strong prior and pulls the final position.
DOMAIN_LEAN = {
    "physics":       1.0,
    "data":          0.7,
    "code":          0.6,
    "information":   0.4,
    "consciousness": 0.1,
    "document":      0.0,
    "media":         0.0,
    "epistemology": -0.1,
    "morality":     -0.6,
    "theology":     -1.0,
    "unknown":       0.0,
}

# ---------------------------------------------------------------------------
# Y axis: how formal the document is as an object
# ---------------------------------------------------------------------------
DOC_TYPE_FORMALITY = {
    "AXIOM":         1.00,
    "DERIVATION":    0.80,
    "CANON":         0.55,
    "BRIDGE":        0.25,
    "EVIDENCE":      0.10,
    "WORKING_NOTE": -0.35,
    "ARTICLE":      -0.70,
    "NARRATIVE":    -1.00,
    # Not points on the axis - placed at the origin and marked visually.
    "DUMP":          0.00,
    "UNCLASSIFIED":  0.00,
    "UNTYPED":       0.00,
    "UNSCANNED":     0.00,
    "UNREADABLE":    0.00,
}

DOC_TYPE_COLORS = {
    "AXIOM":        "#d1a922",
    "CANON":        "#7fd1b9",
    "DERIVATION":   "#6ea8fe",
    "BRIDGE":       "#c792ea",
    "EVIDENCE":     "#ff7b72",
    "NARRATIVE":    "#f0883e",
    "ARTICLE":      "#8ddb8c",
    "WORKING_NOTE": "#94a3b8",
    "DUMP":         "#4b5563",
    "UNCLASSIFIED": "#3f4652",
    "UNTYPED":      "#2f3540",
    "UNSCANNED":    "#2f3540",
    "UNREADABLE":   "#2f3540",
}

MEQ_VARIABLE_NAMES = {
    "G": "Grace / Gravitation",
    "M": "Moral Alignment / Momentum",
    "E": "Truth Signal / EM",
    "S": "Entropy",
    "T": "Time / Relativity",
    "K": "Knowledge / Shannon",
    "R": "Relational Frame",
    "Q": "Quantum / Uncertainty",
    "F": "Faith / Fruit",
    "C": "Christ Alignment / Coherence",
}

MEQ_VARIABLE_COLORS = {
    "G": "#d1a922", "M": "#f0883e", "E": "#6ea8fe", "S": "#ff7b72",
    "T": "#c792ea", "K": "#7fd1b9", "R": "#8ddb8c", "Q": "#79c0ff",
    "F": "#ffa657", "C": "#e6edf3", "none": "#4b5563",
}

# EVIDENCE is sparse in this corpus but high value when it fires, so its dots
# are drawn larger than their confidence alone would justify - a weak EVIDENCE
# call is still worth opening.
EVIDENCE_SIZE_BOOST = 1.6
MIN_MARKER, MAX_MARKER = 6.0, 26.0


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def domain_position(chi: dict, domain_name: str, domain_score: int) -> float:
    """X coordinate: -1 theology ... +1 physics, with bridge material near 0."""
    total = sum(chi.values()) or 0
    chi_lean = (sum(CHI_DOMAIN_LEAN.get(k, 0.0) * v for k, v in chi.items()) / total) if total else 0.0
    prior = DOMAIN_LEAN.get(domain_name, 0.0)
    # The recorded domain is only as trustworthy as its own 0-3 score, so it is
    # weighted by that score rather than assumed.
    w = min(1.0, (domain_score or 0) / 3.0)
    return round(_clamp(chi_lean * (1.0 - 0.5 * w) + prior * 0.5 * w + chi_lean * 0.0), 4)


def formality_position(doc_type: str, type_confidence: float) -> float:
    """
    Y coordinate: -1 narrative ... +1 formal.

    A low-confidence call is pulled toward the origin, so uncertain files sit
    in the middle of the space instead of asserting a position they have not
    earned.
    """
    base = DOC_TYPE_FORMALITY.get(doc_type, 0.0)
    pull = 0.45 + 0.55 * _clamp(float(type_confidence or 0.0), 0.0, 1.0)
    return round(_clamp(base * pull), 4)


def coherence_position(chi: dict, confidence: float) -> float:
    """
    Z coordinate: 0 ... 1 master-equation signal strength.

    Both magnitude (how much CHI signal is present) and spread (how many of the
    ten factors are represented) count - a file scoring high on one factor is
    not as coherent as one that carries the whole equation.
    """
    total   = sum(chi.values())
    nonzero = sum(1 for v in chi.values() if v > 0)
    magnitude = min(1.0, total / 20.0)          # 20 of a possible 30 reads as full
    spread    = nonzero / 10.0
    return round(min(1.0, 0.55 * magnitude + 0.30 * spread + 0.15 * float(confidence or 0.0)), 4)


def marker_size(coherence: float, doc_type: str, size_bytes: int) -> float:
    """Dot size: coherence-led, with the EVIDENCE boost applied on top."""
    size = MIN_MARKER + (MAX_MARKER - MIN_MARKER) * coherence
    if doc_type == "EVIDENCE":
        size *= EVIDENCE_SIZE_BOOST
    return round(min(MAX_MARKER * EVIDENCE_SIZE_BOOST, size), 2)


def marker_opacity(type_confidence: float, doc_type: str) -> float:
    """
    Opacity carries confidence: a weak call must look weak.

    EVIDENCE is floored higher than its confidence would give, because a
    low-confidence EVIDENCE dot is exactly the one worth investigating and it
    must not fade into the background.
    """
    conf = _clamp(float(type_confidence or 0.0), 0.0, 1.0)
    op   = 0.28 + 0.62 * conf
    if doc_type == "EVIDENCE":
        op = max(op, 0.72)
    return round(min(0.95, op), 3)


def top_chi(chi: dict) -> str:
    if not chi or not any(chi.values()):
        return "none"
    return max(chi, key=lambda k: (chi[k], k))


def top_two_chi(chi: dict, threshold: float = 0.3) -> list[str]:
    """
    The two strongest CHI factors, normalised against a 0-3 scale.

    Used to decide graph adjacency: files sharing their top two factors are
    working on the same part of the master equation.
    """
    if not chi:
        return []
    ranked = sorted(chi.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, v in ranked[:2] if (v / 3.0) > threshold]


def fisnote_for(path: Path) -> str:
    """Return the generated .fisnote sidecar text for a file, if one exists."""
    note = path.with_name(path.name + ".fisnote")
    if not note.exists():
        note = path.with_suffix(path.suffix + ".fisnote")
    try:
        return note.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return ""


def folder_page_for(path: Path) -> str:
    """file:// URL of the FIS.html page for the folder holding this file."""
    page = path.parent / "FIS.html"
    return page.as_uri() if page.exists() else ""


def load_points(db_path: Path = DB_DEFAULT, path_prefix: str = "",
                include_untyped: bool = False, with_notes: bool = False) -> list[dict]:
    """
    Read the registry and return one placed point per file.

    This never touches the corpus; it reads what the scan recorded. Files whose
    document type was never scored are excluded by default, because plotting
    them would show absence of data as a position in the space.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    sql = """SELECT file_id, folder_id, path, name, format, size_bytes, last_modified,
                    lossless_address, doc_type, type_confidence, type_scores_json,
                    local_classification_json, keywords_text
             FROM file_memory"""
    params: list = []
    clauses: list[str] = []
    if not include_untyped:
        clauses.append("doc_type NOT IN ('UNSCANNED','UNTYPED','UNREADABLE')")
    if path_prefix:
        clauses.append("path LIKE ?")
        params.append(f"{path_prefix}%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    points = []
    for row in conn.execute(sql, params):
        try:
            local = json.loads(row["local_classification_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            local = {}

        chi = local.get("chi") or {}
        chi = {k: int(v or 0) for k, v in chi.items()}
        domain = local.get("domain") or {}
        law    = local.get("law") or {}

        doc_type = row["doc_type"] or "UNSCANNED"
        conf     = float(row["type_confidence"] or 0.0)
        path     = Path(row["path"])

        x = domain_position(chi, domain.get("name", "unknown"), int(domain.get("score", 0) or 0))
        y = formality_position(doc_type, conf)
        z = coherence_position(chi, float(local.get("confidence", 0.0) or 0.0))

        pt = {
            "file_id":     row["file_id"],
            "name":        row["name"],
            "path":        str(path),
            "folder":      str(path.parent),
            "address":     row["lossless_address"] or "",
            "format":      row["format"],
            "size_bytes":  int(row["size_bytes"] or 0),
            "modified":    row["last_modified"] or "",
            "doc_type":    doc_type,
            "confidence":  round(conf, 3),
            "domain":      domain.get("name", "unknown"),
            "domain_score": int(domain.get("score", 0) or 0),
            "law":         law.get("name", "none"),
            "chi":         chi,
            "chi_sum":     sum(chi.values()),
            "top_chi":     top_chi(chi),
            "top_two":     top_two_chi(chi),
            "evidence_density": local.get("evidence", 0),
            "keywords":    (row["keywords_text"] or "")[:180],
            "x": x, "y": y, "z": z,
            "size":    marker_size(z, doc_type, int(row["size_bytes"] or 0)),
            "opacity": marker_opacity(conf, doc_type),
            "color":   DOC_TYPE_COLORS.get(doc_type, "#4b5563"),
            "page":    folder_page_for(path),
        }
        if with_notes:
            pt["fisnote"] = fisnote_for(path)
        points.append(pt)

    conn.close()
    return points
