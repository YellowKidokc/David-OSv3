"""Document Identity Standard v1.0: validators and registry builder (standard library only).

Nothing here touches source files. `build_registry()` creates a SQLite registry
from registry.sql + registry_rulings.json at a path you choose.
"""
from __future__ import annotations
import json, re, sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
OFFICIAL_REGISTRY = Path("D:/theophysics-data/registry/document_registry.sqlite")  # read-only for apps
DOC_ID = re.compile(r"^(?P<series>[A-Z]{3,5})\.(?P<pos>[0-9]{2})\.(?P<slug>[A-Z0-9]+)$")
ARTIFACT_ROLES = {
    "source", "source.markdown", "source.html", "html.blue", "html.site", "render.blue", "render.site",
    "classify.104", "classify.105", "vector.chi", "vector.namer", "metadata.frontmatter", "metadata.sidecar",
    "audit", "audit.structural", "audit.lawyer", "extract.claims", "extract.evidence", "receipt",
    "receipt.processing", "receipt.move", "formal.lean", "formal.lean_stub", "formal.lean_result",
}
CANON_STATUS = {"NOT_EVALUATED", "CANDIDATE", "EVALUATED", "ADMITTED", "REJECTED", "SUPERSEDED", "WITHDRAWN"}


def position_kind(pos: int) -> str:
    if pos == 0: return "index_or_governing"
    if 1 <= pos <= 79: return "principal"
    if 80 <= pos <= 89: return "companion"
    if 90 <= pos <= 94: return "appendix_or_reference"
    return {95: "concordance", 96: "glossary", 97: "bibliography", 98: "governance", 99: "archive_map"}[pos]


def parse_document_id(doc_id: str) -> dict:
    m = DOC_ID.match(doc_id)
    if not m:
        raise ValueError(f"not SERIES.POSITION.SLUG: {doc_id!r}")
    pos = int(m["pos"])
    return {"series": m["series"], "position": pos, "slug": m["slug"], "kind": position_kind(pos)}


def parse_artifact_ref(ref: str) -> dict:
    parts = ref.split("::")
    if len(parts) not in (2, 3):
        raise ValueError(f"not DOCUMENT_ID::role[::version]: {ref!r}")
    doc = parse_document_id(parts[0])
    if parts[1] not in ARTIFACT_ROLES:
        raise ValueError(f"unknown artifact role {parts[1]!r}")
    return {**doc, "document_id": parts[0], "role": parts[1], "run": parts[2] if len(parts) == 3 else None}


def check_sidecar(sc: dict, approved_admissions: set[str] = frozenset()) -> list[str]:
    """Return safety-rule violations (empty list = OK). Schema shape is checked by sidecar.v1.schema.json."""
    errs = []
    for k in ("document_id", "proposed_document_id"):
        if sc.get(k):
            try: parse_document_id(sc[k])
            except ValueError as e: errs.append(str(e))
    can = sc.get("canonical", {})
    if can.get("canon_status") not in CANON_STATUS:
        errs.append(f"bad canon_status {can.get('canon_status')!r}")
    if can.get("admission_authority") != "DAVID_ONLY":
        errs.append("admission_authority must be DAVID_ONLY")
    if can.get("canon_status") == "ADMITTED":   # rule 1
        ruling = can.get("admitted_by_ruling")
        if not ruling or ruling not in approved_admissions:
            errs.append("ADMITTED without a recorded David ruling (rule 1)")
    phys = sc.get("physical", {})
    if phys.get("move_authorized") and not sc.get("approval_id"):   # rule 5
        errs.append("move_authorized without an approval ledger entry (rule 5)")
    if sc.get("document_id") is None and not sc.get("proposed_document_id"):
        pass  # fine: unidentified file, sidecar only
    return errs


def build_registry(db_path: Path, rulings_path: Path = HERE / "registry_rulings.json") -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.executescript((HERE / "registry.sql").read_text(encoding="utf-8"))
    r = json.loads(rulings_path.read_text(encoding="utf-8"))
    with con:
        for sid, s in r["series"].items():
            con.execute("INSERT OR IGNORE INTO series(series_id, canonical_title, member_count) VALUES (?,?,?)",
                        (sid, s["canonical_title"], len(s["members"])))
            for doc_id, title in s["members"].items():
                d = parse_document_id(doc_id)
                assert d["series"] == sid, doc_id
                status = "displaced" if doc_id in s.get("displaced", []) else \
                         "planned" if doc_id in s.get("planned", []) else "assigned"
                con.execute("INSERT OR IGNORE INTO documents(document_id, canonical_title, series_id, position, slug, status, note) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (doc_id, title, sid, d["position"], d["slug"], status, s.get("notes", {}).get(doc_id)))
        for a, rel, b in r["relations"]:
            con.execute("INSERT OR IGNORE INTO relations VALUES (?,?,?)", (a, rel, b))
    return con
