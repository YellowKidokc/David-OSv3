"""File Operations catalog — each op is a first-class thing with its own WARNINGS.

A GUI/Excel button for an operation shows what it does AND what to watch out for
BEFORE it runs. Running `dedupe` surfaces its warnings and the follow-on
operations to expect. Operations read from the SQLite store (the cache), not by
re-walking the drives.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Operation:
    op_id: str                       # "sim/dedupe"
    code: str                        # lok|idn|und|sim|dec|act|gov|lrn|aut
    name: str                        # button label
    summary: str
    reads_from: str = "sqlite_store" # scan the DB, not the drives
    mutating: bool = False
    warnings: list[str] = field(default_factory=list)      # things to watch out for
    watch_for: list[str] = field(default_factory=list)     # anomalies this op can cause
    follow_ops: list[str] = field(default_factory=list)    # what usually comes next


CATALOG: dict[str, Operation] = {
    "lok/search": Operation(
        "lok/search", "lok", "Search", "Find files matching a query across scope.",
        warnings=["Runs against the SQLite index, not the live disk — re-scan if stale."],
        watch_for=["Loose matches (aliases) may pull in out-of-range files — review them."],
        follow_ops=["cut", "assess_series"]),
    "dec/cut": Operation(
        "dec/cut", "dec", "Cut / Aggregate", "Collect a set of files into one folder.",
        warnings=["Originals move unless mode=copy.", "Requires approval before execution."],
        watch_for=["Name collisions are auto-suffixed — verify nothing important is renamed."],
        follow_ops=["dedupe", "categorize"]),
    "dec/breakdown": Operation(
        "dec/breakdown", "dec", "Break Down / Flatten", "Strip a tree to individual files.",
        warnings=["Flattening LOSES folder context — preserve the original path in the .fisnote.",
                  "Never flatten a program/project root (red) — dependencies break."],
        watch_for=["Intentional folder structure (a series' chapter order) may be destroyed."],
        follow_ops=["dedupe", "categorize"]),
    "sim/dedupe": Operation(
        "sim/dedupe", "sim", "Dedupe", "Group identical files, keep one, quarantine the rest.",
        warnings=["Hash before any delete.", "Always keep at least one copy.",
                  "Protected/red items are excluded.", "Quarantine — never hard-delete."],
        watch_for=["A duplicate across working / backup / publication may be an INTENTIONAL mirror — ask first.",
                   "Near-duplicates (edited versions) are NOT exact dupes — do not merge blindly."],
        follow_ops=["review_keepers"]),
}


def get(op_id: str) -> Operation | None:
    return CATALOG.get(op_id)


def buttons() -> list[dict]:
    """What a GUI/Excel would render — label + its warning panel."""
    return [{"op_id": o.op_id, "code": o.code, "name": o.name, "summary": o.summary,
             "mutating": o.mutating, "warnings": o.warnings, "watch_for": o.watch_for,
             "follow_ops": o.follow_ops} for o in CATALOG.values()]
