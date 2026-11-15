"""gate_events — turns gate override ledger rows into harness Events.

The gate is never the final authority: every ASK the user answers is a ruling,
and rulings are what the engines learn from. Re-runs never double-count —
ids are content hashes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 02_CLASSIFICATION
from harness.contract import Event  # noqa: E402

WATCHED = ("gate_override", "gate_decision")


def _row_to_event(row: dict) -> Event | None:
    if row.get("event") not in WATCHED:
        return None
    folder = row.get("folder") or str(Path(row.get("path", ".")).parent)
    raw = json.dumps(row, sort_keys=True)
    return Event(
        subject=folder,
        action="gate:" + row["event"].removeprefix("gate_"),
        context={"action_id": row.get("action_id", ""), "verdict": row.get("verdict", ""),
                 "choice": row.get("choice", "")},
        source="gate",
        timestamp=row.get("ts", ""),
        id="go-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12],
    )


def read(ledger_path: str | Path) -> list[Event]:
    p = Path(ledger_path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = _row_to_event(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip torn writes, never die on the ledger
        if ev:
            out.append(ev)
    return out


if __name__ == "__main__":
    from harness.runner import Runner
    repo = Path(__file__).resolve().parents[4]  # David-OSv3
    evs = read(repo / "system" / "ledger" / "file_events.jsonl")
    n = Runner(db_path=Path(__file__).resolve().parents[1] / "data" / "gate.db",
               context_keys=("action_id",)).ingest(evs)
    print(f"ingested {n} gate events")
