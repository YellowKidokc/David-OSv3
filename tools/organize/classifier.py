#!/usr/bin/env python3
"""Learning chi classifier: rules first, LLM fallback below threshold."""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import sqlite3
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

DB_PATH = Path(os.environ.get("CHI_DB_PATH", Path(__file__).with_name("organize.db")))
SEED_PATH = Path(__file__).with_name("seed_rules.json")
THRESHOLD = 0.85

SCHEMA = """
CREATE TABLE IF NOT EXISTS classification_rules (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT NOT NULL,
    pattern TEXT NOT NULL,
    primary_chi TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    hit_count INTEGER DEFAULT 0,
    accept_count INTEGER DEFAULT 0,
    reject_count INTEGER DEFAULT 0,
    created TEXT DEFAULT (datetime('now')),
    UNIQUE(pattern_type, pattern, primary_chi)
);
CREATE TABLE IF NOT EXISTS classification_history (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    suggested_chi TEXT,
    accepted_chi TEXT,
    confidence REAL,
    method TEXT,
    created TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rules_pattern ON classification_rules(pattern_type, pattern);
CREATE INDEX IF NOT EXISTS idx_history_file ON classification_history(file_name);
"""

CHI_FACTORS = """
G - Gravity/Grace/Authority: foundation, substrate, canonical authority, source
M - Motion/Alignment/Mechanism: process, workflow, causal machinery, tools
E - Truth/Signal: truth, deception, signal fidelity, Shannon, publication, light
S - Entropy/Judgment/Decay: disorder, repair, thermodynamic correction, decline
T - Time/Sequence: timeline, prophecy, before/after, version order, temporal data
K - Knowledge/Logos/Information: definitions, equations, compression, structured claims
R - Relation/Binding: covenant, love, dependency, relational structure, connection
Q - Quantum/Faith: uncertainty, collapse, commitment, observer, faith under uncertainty
F - Weak/Sin Conservation: atonement, deficit, displacement, hidden moral debt
C - Coherence/Christ: integration, whole-system unity, no-drift topology
CHI - Master Integration: full synthesis, all-law maps, whole-framework
"""


def connect_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.executescript(SCHEMA)
    db.commit()
    seed_rules(db)
    return db


def seed_rules(db: sqlite3.Connection) -> None:
    if not SEED_PATH.exists():
        return
    rules = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for pattern_type, pattern, primary_chi, weight in rules:
        db.execute(
            """INSERT OR IGNORE INTO classification_rules
               (pattern_type, pattern, primary_chi, weight)
               VALUES (?, ?, ?, ?)""",
            (pattern_type, pattern, primary_chi, weight),
        )
    db.commit()


def content_preview(path: Path, limit: int = 1200) -> str:
    if not path.exists() or not path.is_file():
        return ""
    if path.stat().st_size > 5 * 1024 * 1024:
        limit = 500
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def rule_matches(row: sqlite3.Row, path: Path, preview: str) -> bool:
    ptype = row["pattern_type"]
    pattern = row["pattern"]
    path_text = str(path)
    name_text = path.name.lower()
    pattern_lower = pattern.lower()
    if ptype == "extension":
        return path.suffix.lower() == pattern_lower
    if ptype == "keyword":
        return pattern_lower in name_text or pattern_lower in preview.lower()
    if ptype == "path":
        return pattern_lower in path_text.lower()
    if ptype == "content":
        return pattern_lower in preview.lower()
    return False


def classify_by_rules(db: sqlite3.Connection, file_path: str) -> tuple[str, float, str, list[int]]:
    path = Path(file_path)
    preview = content_preview(path)
    rows = db.execute("SELECT * FROM classification_rules").fetchall()
    scores: dict[str, float] = defaultdict(float)
    match_counts: dict[str, int] = defaultdict(int)
    matched_ids: list[int] = []
    methods = set()

    for row in rows:
        if not rule_matches(row, path, preview):
            continue
        matched_ids.append(row["id"])
        methods.add(row["pattern_type"])
        reliability = (row["accept_count"] + 1) / (row["accept_count"] + row["reject_count"] + 2)
        score = float(row["weight"]) * (0.65 + reliability)
        scores[row["primary_chi"]] += score
        match_counts[row["primary_chi"]] += 1

    if not scores:
        return "", 0.0, "none", []

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_chi, top_score = ranked[0]
    if len(matched_ids) == 1:
        confidence = min(0.84, 0.35 + (top_score * 0.35))
        method = "+".join(sorted(methods))
        return top_chi, round(confidence, 2), method or "rule", matched_ids
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    support = min(0.22, math.log1p(top_score) / 5)
    margin = (top_score - second) / max(top_score, 0.01)
    reinforcement = min(0.08, max(0, match_counts[top_chi] - 1) * 0.04)
    confidence = max(0.0, min(0.99, 0.58 + support + (0.23 * margin) + reinforcement))
    method = "+".join(sorted(methods))
    return top_chi, round(confidence, 2), method or "rule", matched_ids


def llm_classify(file_path: str) -> dict:
    path = Path(file_path)
    preview = content_preview(path, 700)
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package missing; install it or accept queued rule suggestions manually") from exc

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=os.environ.get("CHI_LLM_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""Classify this file by which chi factor it most serves.

Filename: {path.name}
Path: {path}
Content preview: {preview[:500]}

Chi factors:
{CHI_FACTORS}

Respond in JSON only:
{{"primary": "X", "secondary": ["Y","Z"], "confidence": 0.XX, "reason": "brief reason"}}"""
        }],
    )
    text = response.content[0].text.strip()
    return json.loads(text)


def log_history(db: sqlite3.Connection, file_path: str, suggested: str, confidence: float, method: str) -> int:
    path = Path(file_path)
    cur = db.execute(
        """INSERT INTO classification_history
           (file_path, file_name, suggested_chi, accepted_chi, confidence, method)
           VALUES (?, ?, ?, NULL, ?, ?)""",
        (str(path), path.name, suggested, confidence, method),
    )
    db.commit()
    return int(cur.lastrowid)


def classify(file_path: str) -> None:
    db = connect_db()
    try:
        suggested, confidence, method, matched_ids = classify_by_rules(db, file_path)
        for rule_id in matched_ids:
            db.execute("UPDATE classification_rules SET hit_count=hit_count+1 WHERE id=?", (rule_id,))
        if confidence >= THRESHOLD:
            row_id = log_history(db, file_path, suggested, confidence, method)
            db.execute("UPDATE classification_history SET accepted_chi=? WHERE id=?", (suggested, row_id))
            db.commit()
            print(f"{suggested} (confidence: {confidence:.0%}, method: {method})")
            return

        llm_note = ""
        if suggested:
            method = f"{method}+llm_pending"
        else:
            method = "llm_pending"
        try:
            result = llm_classify(file_path)
            suggested = result.get("primary") or suggested
            confidence = float(result.get("confidence") or confidence)
            llm_note = f" - LLM suggests: {suggested} {result.get('reason', '')}".strip()
            method = "llm"
        except Exception as exc:
            llm_note = f" - LLM unavailable: {exc}"

        row_id = log_history(db, file_path, suggested, confidence, method)
        print(f"{suggested or '?'} (confidence: {confidence:.0%}, method: {method}) - BELOW THRESHOLD")
        print(f"Queued review id={row_id}{llm_note}")
    finally:
        db.close()


def review() -> None:
    db = connect_db()
    try:
        rows = db.execute(
            """SELECT id, file_path, suggested_chi, confidence, method, created
               FROM classification_history
               WHERE accepted_chi IS NULL
               ORDER BY created DESC"""
        ).fetchall()
        if not rows:
            print("No pending reviews.")
            return
        for row in rows:
            print(f"{row['id']:>4}  {row['suggested_chi'] or '?':<3}  {row['confidence'] or 0:.0%}  {row['method']:<14}  {row['file_path']}")
    finally:
        db.close()


def accept(row_id: int, chi: str) -> None:
    db = connect_db()
    try:
        row = db.execute("SELECT * FROM classification_history WHERE id=?", (row_id,)).fetchone()
        if not row:
            raise SystemExit(f"No classification_history id={row_id}")
        db.execute("UPDATE classification_history SET accepted_chi=? WHERE id=?", (chi, row_id))
        path = Path(row["file_path"])
        ext = path.suffix.lower()
        if ext:
            db.execute(
                """INSERT INTO classification_rules (pattern_type, pattern, primary_chi, weight, accept_count)
                   VALUES ('extension', ?, ?, 0.5, 1)
                   ON CONFLICT(pattern_type, pattern, primary_chi)
                   DO UPDATE SET accept_count=accept_count+1, weight=min(weight+0.05, 3.0)""",
                (ext, chi),
            )
        for token in path.stem.replace("-", "_").split("_"):
            if len(token) >= 4 and token.isalpha():
                db.execute(
                    """INSERT INTO classification_rules (pattern_type, pattern, primary_chi, weight, accept_count)
                       VALUES ('keyword', ?, ?, 0.4, 1)
                       ON CONFLICT(pattern_type, pattern, primary_chi)
                       DO UPDATE SET accept_count=accept_count+1, weight=min(weight+0.03, 3.0)""",
                    (token.lower(), chi),
                )
        if row["suggested_chi"] and row["suggested_chi"] != chi:
            db.execute("UPDATE classification_rules SET reject_count=reject_count+1 WHERE primary_chi=?", (row["suggested_chi"],))
        db.commit()
        train(silent=True)
        print(f"Accepted id={row_id} as {chi}")
    finally:
        db.close()


def train(silent: bool = False) -> None:
    db = connect_db()
    try:
        rows = db.execute(
            "SELECT suggested_chi, accepted_chi FROM classification_history WHERE accepted_chi IS NOT NULL"
        ).fetchall()
        for row in rows:
            if not row["suggested_chi"]:
                continue
            if row["suggested_chi"] == row["accepted_chi"]:
                db.execute(
                    "UPDATE classification_rules SET accept_count=accept_count+1, weight=min(weight+0.01, 3.0) WHERE primary_chi=?",
                    (row["accepted_chi"],),
                )
            else:
                db.execute(
                    "UPDATE classification_rules SET reject_count=reject_count+1, weight=max(weight-0.01, 0.05) WHERE primary_chi=?",
                    (row["suggested_chi"],),
                )
        db.commit()
        if not silent:
            print(f"Training pass complete: {len(rows)} accepted history rows")
    finally:
        db.close()


def export_xlsx(path: str) -> None:
    db = connect_db()
    try:
        rules = [dict(r) for r in db.execute("SELECT * FROM classification_rules ORDER BY pattern_type, pattern, primary_chi")]
        history = [dict(r) for r in db.execute("SELECT * FROM classification_history ORDER BY created DESC")]
    finally:
        db.close()
    write_xlsx(Path(path), {"rules": rules, "history": history})
    print(f"Exported {path}")


def col_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def sheet_xml(rows: list[dict]) -> str:
    headers = list(rows[0].keys()) if rows else ["empty"]
    xml_rows = []
    for r_idx, values in enumerate([dict(zip(headers, headers))] + rows, start=1):
        cells = []
        for c_idx, header in enumerate(headers, start=1):
            value = "" if values.get(header) is None else str(values.get(header))
            ref = f"{col_name(c_idx)}{r_idx}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{html.escape(value)}</t></is></c>')
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'


def write_xlsx(path: Path, sheets: dict[str, list[dict]]) -> None:
    sheet_names = list(sheets)
    workbook_sheets = "".join(
        f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    rels = "".join(
        f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        for idx, _ in enumerate(sheet_names, start=1)
    )
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx, _ in enumerate(sheet_names, start=1)
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>{overrides}</Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        for idx, name in enumerate(sheet_names, start=1):
            z.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml(sheets[name]))


def import_rules(path: str) -> None:
    src = Path(path)
    rows = []
    if src.suffix.lower() == ".csv":
        with src.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    else:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise SystemExit("Import .xlsx needs openpyxl. Export works without it; import CSV works now.") from exc
        wb = load_workbook(src)
        ws = wb["rules"] if "rules" in wb.sheetnames else wb.active
        headers = [c.value for c in next(ws.iter_rows(max_row=1))]
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append(dict(zip(headers, row)))
    db = connect_db()
    try:
        count = 0
        for row in rows:
            if not row.get("pattern_type") or not row.get("pattern") or not row.get("primary_chi"):
                continue
            db.execute(
                """INSERT INTO classification_rules
                   (pattern_type, pattern, primary_chi, weight, hit_count, accept_count, reject_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(pattern_type, pattern, primary_chi) DO UPDATE SET
                    weight=excluded.weight, hit_count=excluded.hit_count,
                    accept_count=excluded.accept_count, reject_count=excluded.reject_count""",
                (
                    row["pattern_type"],
                    row["pattern"],
                    row["primary_chi"],
                    float(row.get("weight") or 1.0),
                    int(row.get("hit_count") or 0),
                    int(row.get("accept_count") or 0),
                    int(row.get("reject_count") or 0),
                ),
            )
            count += 1
        db.commit()
        print(f"Imported {count} rules")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Learning chi file classifier.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    classify_p = sub.add_parser("classify")
    classify_p.add_argument("file")
    sub.add_parser("review")
    accept_p = sub.add_parser("accept")
    accept_p.add_argument("id", type=int)
    accept_p.add_argument("chi")
    sub.add_parser("train")
    export_p = sub.add_parser("export")
    export_p.add_argument("path", nargs="?", default="classification_export.xlsx")
    import_p = sub.add_parser("import")
    import_p.add_argument("path")
    args = parser.parse_args()

    if args.cmd == "classify":
        classify(args.file)
    elif args.cmd == "review":
        review()
    elif args.cmd == "accept":
        accept(args.id, args.chi)
    elif args.cmd == "train":
        train()
    elif args.cmd == "export":
        export_xlsx(args.path)
    elif args.cmd == "import":
        import_rules(args.path)


if __name__ == "__main__":
    main()
