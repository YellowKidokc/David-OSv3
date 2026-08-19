#!/usr/bin/env python3
"""fis_markov_bridge.py - feed approval decisions into the X-drive Markov chains.

Chains DB: X:\\09_DATABASES\\FIS\\preference_engine.db (P07 markovify family).
Actual schema (verified 2026-08-04):
  decisions(id, filename, extension, keywords, proposed_domain, final_domain,
            confidence, action, source, timestamp)
  keyword_chains(keyword, domain, count, last_seen)
  ext_chains(extension, domain, count)
  correction_matrix(from_domain, to_domain, count)

Every approve/reject/edit in the approval GUI lands here so keyword->domain and
ext->domain counts strengthen with use. Fails silently if X: is offline - the
local River engine and the jsonl ledger still learn/record regardless.
"""
from __future__ import annotations
import re, sqlite3, time
from pathlib import Path

CHAIN_DB = Path(r"X:\09_DATABASES\FIS\preference_engine.db")
STOP = {"the", "and", "for", "with", "from", "this", "that", "file", "copy", "new", "final"}


def _keywords(name: str):
    return [w for w in re.findall(r"[a-z0-9]{3,}", name.lower()) if w not in STOP][:8]


def record_decision(proposal: dict, decision: str) -> bool:
    """decision: approved | rejected | edited. Returns True if chains updated."""
    if not CHAIN_DB.exists():
        return False
    name = (proposal.get("proposed_name") or proposal.get("new_name")
            or proposal.get("current_name") or proposal.get("old_name") or "")
    ext = Path(name).suffix.lower()
    kws = _keywords(Path(name).stem)
    proposed_domain = proposal.get("domain") or proposal.get("proposed_domain") or "rename"
    final_domain = proposed_domain if decision != "rejected" else "rejected"
    now = time.time()
    try:
        con = sqlite3.connect(CHAIN_DB, timeout=5)
        con.execute(
            "INSERT INTO decisions(filename, extension, keywords, proposed_domain,"
            " final_domain, confidence, action, source, timestamp)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (name, ext, " ".join(kws), proposed_domain, final_domain,
             proposal.get("predicted_approval"), decision, "approval-gui", now))
        if decision != "rejected":
            for kw in kws:
                cur = con.execute(
                    "UPDATE keyword_chains SET count=count+1, last_seen=? WHERE keyword=? AND domain=?",
                    (now, kw, final_domain))
                if cur.rowcount == 0:
                    con.execute("INSERT INTO keyword_chains(keyword,domain,count,last_seen) VALUES(?,?,1,?)",
                                (kw, final_domain, now))
            if ext:
                cur = con.execute("UPDATE ext_chains SET count=count+1 WHERE extension=? AND domain=?",
                                  (ext, final_domain))
                if cur.rowcount == 0:
                    con.execute("INSERT INTO ext_chains(extension,domain,count) VALUES(?,?,1)",
                                (ext, final_domain))
        if decision == "edited":
            cur = con.execute(
                "UPDATE correction_matrix SET count=count+1 WHERE from_domain=? AND to_domain=?",
                (proposed_domain, final_domain))
            if cur.rowcount == 0:
                con.execute("INSERT INTO correction_matrix(from_domain,to_domain,count) VALUES(?,?,1)",
                            (proposed_domain, final_domain))
        con.commit(); con.close()
        return True
    except Exception:
        return False
