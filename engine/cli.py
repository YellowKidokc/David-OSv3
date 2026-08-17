"""
cli.py — command-line entry point for the File Intelligence System (MVP backbone).

Commands:
  scan    walk roots -> fingerprint -> classify -> propose names -> store + report
  report  regenerate the CSV + HTML from the existing DB
  status  show DB counts + preference-engine stats
  learn   feed an edited approval_queue.csv back into the preference engine

PROPOSE-ONLY: no command renames, moves, or deletes any file.

Usage:
  python src/cli.py scan --roots ./sample --types .md .txt
  python src/cli.py report
  python src/cli.py status
  python src/cli.py learn --csv system/reports/approval_queue.csv
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import inventory_scan
import report_builder
import metadata_db as db


def cmd_scan(args):
    cfg = config.ScanConfig(
        scan_roots=args.roots,
        file_types=[t if t.startswith(".") else f".{t}" for t in args.types],
        db_path=args.db or str(config.DB_PATH),
        max_files=args.limit,
    )
    print(f"Scanning {len(cfg.scan_roots)} root(s): {cfg.scan_roots}")
    print(f"File types: {cfg.file_types}")
    print(f"DB: {cfg.db_path}")

    records, folder_symptoms, summary = inventory_scan.scan(
        cfg, progress_cb=lambda n, f: print(f"  [{n}] {f}"))

    print(f"\nScanned {summary['file_count']} files")
    print(f"  Domains:        {summary['domains']}")
    print(f"  Content types:  {summary['content_types']}")
    print(f"  Decisions:      {summary['decisions']}")
    print(f"  Enriched (low-conf): {summary.get('enriched', 0)}")
    print(f"  Folders w/ symptoms: {summary['folders_with_symptoms']}")
    if summary.get("gate_routes"):
        print(f"  Gate routes:    {summary['gate_routes']}")
        print(f"  Gate tiers:     {summary['gate_tiers']}  (markov-smoothed: {summary.get('gate_smoothed', 0)})")
        if summary.get("needs_access"):
            print("  PROVISIONING CHECKLIST (blocked, needs access):")
            for cat, srcs in summary["needs_access"].items():
                print(f"    - {cat}: {', '.join(srcs)}")

    if summary["file_count"]:
        out = report_builder.build_all(folder_symptoms, db_path=cfg.db_path)
        print(f"\nReports:\n  CSV : {out['csv']}\n  HTML: {out['html']}")
        print("Review the CSV, fill the APPROVE column, then: python src/cli.py learn --csv <file>")


def cmd_report(args):
    out = report_builder.build_all(db_path=args.db or str(config.DB_PATH))
    print(f"CSV : {out['csv']}\nHTML: {out['html']}")


def cmd_status(args):
    con = db.connect(args.db or str(config.DB_PATH))
    try:
        print("DB counts:", db.counts(con))
    finally:
        con.close()
    from preference_engine import get_engine
    st = get_engine().stats()
    print(f"\nEnsemble: mode={st['mode']} n_seen={st['n_seen']}")
    for e in st["engines"]:
        flag = "ok " if e.get("available") else "OFF"
        extra = f"  ({e['hint']})" if e.get("hint") else ""
        print(f"  [{flag}] {e['name']:22} n_seen={e['n_seen']:<4} ready={e['ready']}{extra}")


def cmd_compare(args):
    from preference.ensemble import backtest, DECISION_LOG
    rows = backtest()
    if not rows:
        print(f"No decision history yet at {DECISION_LOG}.")
        print("Approve some files first: review approval_queue.csv, then `learn`.")
        return
    print(f"Backtest on {rows[0].get('n', 0)} logged decisions "
          f"(prequential predict-then-learn):\n")
    print(f"  {'engine':24} {'acc(all)':>9} {'acc(warm)':>10} {'logloss':>8}")
    for r in rows:
        if not r.get("available"):
            print(f"  {r['engine']:24} {'—':>9} {'—':>10} {'—':>8}  (unavailable)")
            continue
        aw = r["acc_warm"] if r["acc_warm"] is not None else "—"
        print(f"  {r['engine']:24} {r['acc_all']:>9} {str(aw):>10} {r['logloss']:>8}")
    print("\nacc(warm) = accuracy after the engine passed its MIN_SAMPLES warm-up — the fair number.")


def cmd_learn(args):
    import csv as _csv
    from preference_engine import get_engine
    import ledger
    engine = get_engine()
    con = db.connect(args.db or str(config.DB_PATH))
    learned = 0
    try:
        with open(args.csv, encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                decision = (row.get("APPROVE") or "").strip().lower()
                if decision not in ("yes", "no", "y", "n"):
                    continue
                approved = decision in ("yes", "y")
                name = row.get("proposed_name") or ""
                fields = name.split("__")
                proposal = {
                    "proposed_name": name,
                    "domain_code": fields[0] if fields else "GN",
                    "ct_code": fields[1] if len(fields) > 1 else "DOC",
                    "tags": fields[2].split("-") if len(fields) > 2 else [],
                    "status_code": fields[4].split(".")[0] if len(fields) > 4 else "AC",
                }
                engine.learn(proposal, approved=approved, note=row.get("notes", ""))
                # write the decision back into filebrain so the approved corpus grows
                # (this is what the enricher matches future low-confidence files against)
                path = row.get("path")
                if path:
                    user_note = (row.get("notes") or "").strip()
                    if user_note:
                        # append the user's note; never clobber system-stamped notes
                        con.execute(
                            "UPDATE files SET approved=?, "
                            "notes=TRIM(COALESCE(notes,'') || ' [user] ' || ?) WHERE path=?",
                            (1 if approved else 0, user_note, path))
                    else:
                        con.execute("UPDATE files SET approved=? WHERE path=?",
                                    (1 if approved else 0, path))
                    ledger.log_rename("approved" if approved else "rejected",
                                      row.get("current_name", ""), name)
                learned += 1
        con.commit()
    finally:
        con.close()
    engine.save()
    print(f"Learned {learned} decisions (written back to DB). {engine.stats()}")


def main():
    p = argparse.ArgumentParser(description="File Intelligence System (propose-only MVP)")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("scan", help="Scan, classify, and propose names")
    s.add_argument("--roots", nargs="+", required=True)
    s.add_argument("--types", nargs="+", default=[".md", ".txt", ".html"])
    s.add_argument("--db", default=None)
    s.add_argument("--limit", type=int, default=0, help="Max files to scan (0=unlimited)")
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("report", help="Regenerate CSV + HTML from the DB")
    r.add_argument("--db", default=None)
    r.set_defaults(func=cmd_report)

    st = sub.add_parser("status", help="Show DB + preference engine stats")
    st.add_argument("--db", default=None)
    st.set_defaults(func=cmd_status)

    cp = sub.add_parser("compare", help="Backtest every preference engine on the decision log")
    cp.set_defaults(func=cmd_compare)

    l = sub.add_parser("learn", help="Feed an edited approval_queue.csv to the preference engine")
    l.add_argument("--csv", required=True)
    l.add_argument("--db", default=None)
    l.set_defaults(func=cmd_learn)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
