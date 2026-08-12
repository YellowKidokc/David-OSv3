# fis-op: pipeline
"""fis_engine — the universal file-job pipeline.

Every operation (search, copy, move, aggregate, flatten, dedupe, organize,
archive, quarantine) is ONE governed job through ONE grammar:

    find -> identify -> relate -> protect -> clarify
         -> propose -> authorize -> execute -> verify -> remember

Only the JobSpec changes between tasks. Mutation happens ONLY when
    job.apply AND job.approved AND no blocking anomaly.
Default is preview-only. The executor copies (preserves originals) unless told
otherwise, verifies by hash, and writes a rollback manifest + ledger.

Stages are wired to the real FIS modules (series corroboration, classify,
learned policies) — not stubs.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from . import scan as scan_mod, series as series_mod, rulings as rulings_mod


# ---------------------------------------------------------------- vocabulary
class Operation(str, Enum):
    SCAN = "scan"; COPY = "copy"; MOVE = "move"; RENAME = "rename"
    AGGREGATE = "aggregate"; FLATTEN = "flatten"; DEDUPLICATE = "deduplicate"
    ORGANIZE = "organize"; ARCHIVE = "archive"; QUARANTINE = "quarantine"; REPORT = "report"


class Strategy(str, Enum):
    FLAT = "flat"; EXTENSION = "extension"; SEMANTIC = "semantic"
    SERIES_THEN_FORMAT = "series_then_format"


class State(str, Enum):
    PROPOSED = "proposed"; BLOCKED = "blocked"; APPROVED = "approved"
    REJECTED = "rejected"; EXECUTED = "executed"; FAILED = "failed"


# ---------------------------------------------------------------- contracts
@dataclass
class FileRecord:
    object_id: str
    source_path: str
    name: str
    extension: str
    size: int
    modified_ns: int
    sha256: str | None = None
    content_type: str | None = None
    role: str | None = None
    protected: bool = False
    protection_reason: str | None = None
    membership_score: float = 0.0
    ownership_prob: float = 0.0
    duplicate_group: str | None = None
    identity: str | None = None
    proposed_path: str | None = None


@dataclass
class Anomaly:
    anomaly_id: str
    anomaly_type: str
    severity: str
    message: str
    object_ids: list[str] = field(default_factory=list)
    possible_answers: list[str] = field(default_factory=list)
    blocking: bool = False
    resolved: bool = False
    ruling: str | None = None


@dataclass
class ProposedAction:
    action_id: str
    operation: Operation
    source: str
    target: str | None
    object_id: str
    original_path: str
    confidence: float
    authorized: bool = False
    state: State = State.PROPOSED


@dataclass
class FileJob:
    job_id: str
    name: str
    roots: list[str]
    destination: str
    operations: list[Operation]
    strategy: Strategy = Strategy.SERIES_THEN_FORMAT
    aliases: list[str] = field(default_factory=list)
    accept_threshold: float = 0.6
    review_threshold: float = 0.2
    preserve_originals: bool = True         # copy, not move
    flatten: bool = True
    exact_dedupe: bool = True
    apply: bool = False                     # <- mutation gate 1 (default OFF)
    approved: bool = False                  # <- mutation gate 2 (default OFF)
    rulings_path: str | None = None


@dataclass
class JobResult:
    job: FileJob
    records: list[FileRecord]
    anomalies: list[Anomaly]
    actions: list[ProposedAction]
    summary: dict = field(default_factory=dict)
    executed: int = 0
    failed: int = 0


# ---------------------------------------------------------------- safety
PROTECTED_NAMES = {".git", ".env", "node_modules", "venv", ".venv", "__pycache__"}
PROTECTED_EXTS = {".key", ".pem", ".pfx", ".db", ".sqlite", ".pst", ".secret"}
SYSTEM_MARKERS = {"windows", "program files", "programdata", "appdata"}


def protection_reason(path: Path) -> str | None:
    parts = {p.lower() for p in path.parts}
    if parts & SYSTEM_MARKERS:
        return "system_path"
    if any(p.lower() in PROTECTED_NAMES for p in path.parts):
        return "project_or_secret_marker"
    if path.suffix.lower() in PROTECTED_EXTS:
        return "protected_extension"
    if any(k in path.name.lower() for k in ("secret", "token", "credential", "password")):
        return "secret_name"
    return None


def _sha(path: Path, chunk=1 << 20) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while b := f.read(chunk):
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------- stages
def _find(job: FileJob) -> list[FileRecord]:
    out = []
    for root_text in job.roots:
        root = Path(root_text)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            r = protection_reason(p)
            out.append(FileRecord(
                object_id=uuid.uuid4().hex, source_path=str(p), name=p.name,
                extension=p.suffix.lower(), size=st.st_size, modified_ns=st.st_mtime_ns,
                content_type=scan_mod.content_type_for(p.name, False),
                protected=r is not None, protection_reason=r))
    return out


def _identify(records: list[FileRecord]) -> None:
    # size-group first, hash only possible duplicate groups (efficient)
    by_size: dict[int, list[FileRecord]] = defaultdict(list)
    for r in records:
        by_size[r.size].append(r)
    for group in by_size.values():
        if len(group) > 1:
            for r in group:
                if r.size <= 32_000_000:
                    r.sha256 = _sha(Path(r.source_path))


def _membership_score(rec: FileRecord, aliases: list[str]) -> float:
    name = rec.name.lower()
    path = rec.source_path.lower()
    text = ""
    if rec.content_type in ("markdown", "text", "code", "data"):
        try:
            with open(rec.source_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(6000).lower()
        except OSError:
            pass
    score = 0.0
    for a in aliases:
        a = a.lower()
        if a in name:
            score += 0.5
        elif a in path:
            score += 0.25
        elif a in text:
            score += 0.2
    return min(1.0, score)


def _understand(job: FileJob, records: list[FileRecord]) -> None:
    for rec in records:
        if rec.protected:
            rec.role = "protected"
            continue
        rec.membership_score = _membership_score(rec, job.aliases)


def _relate(job: FileJob, records: list[FileRecord]) -> None:
    """Exact-dup groups + series corroboration (recurrence across folders boosts ownership)."""
    # exact duplicate groups
    groups: dict[str, list[FileRecord]] = defaultdict(list)
    for r in records:
        if r.sha256:
            groups[r.sha256].append(r)
    n = 1
    for matches in groups.values():
        if len(matches) > 1:
            gid = f"DUP-{n:05d}"; n += 1
            for r in matches:
                r.duplicate_group = gid
    # corroboration: identity by sha (or normalized name), boosted by #distinct folders
    ident_folders: dict[str, set] = defaultdict(set)
    ident_recs: dict[str, list[FileRecord]] = defaultdict(list)
    for r in records:
        if r.membership_score < job.review_threshold:
            continue
        ident = ("h:" + r.sha256[:16]) if r.sha256 else \
                ("n:" + "".join(ch for ch in r.name.lower() if ch.isalnum()))
        r.identity = ident
        ident_folders[ident].add(os.path.dirname(r.source_path))
        ident_recs[ident].append(r)
    for ident, recs in ident_recs.items():
        base = max(x.membership_score for x in recs)
        folders = len(ident_folders[ident])
        prob = min(0.99, 1 - (1 - base) * (series_mod.DECAY ** (folders - 1)))
        for r in recs:
            r.ownership_prob = round(prob, 3)


def _assign_roles(job: FileJob, records: list[FileRecord]) -> None:
    for r in records:
        if r.protected:
            r.role = "protected"
        elif r.ownership_prob >= job.accept_threshold or r.membership_score >= job.accept_threshold:
            r.role = "series_member"
        elif r.membership_score >= job.review_threshold:
            r.role = "possible_series_member"
        else:
            r.role = "outside_collection"


def _clarify(job: FileJob, records: list[FileRecord]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    # apply learned policies first — answered questions stay answered
    store = rulings_mod.RulingStore(job.rulings_path or (Path("_atlas_out") / "rulings.jsonl"))

    # ONE boundary question for all uncertain members (not one per file)
    uncertain = [r for r in records if r.role == "possible_series_member"]
    if uncertain:
        anomalies.append(Anomaly(
            anomaly_id=uuid.uuid4().hex, anomaly_type="uncertain_membership", severity="medium",
            message=f"{len(uncertain)} files loosely match — include in the collection?",
            object_ids=[r.object_id for r in uncertain],
            possible_answers=["Include", "Exclude", "Show examples", "Apply to similar"],
            blocking=False))

    # authority markers -> blocking, unless a learned policy already resolved it
    marked = [r for r in records if any(m in r.name.upper()
              for m in ("FINAL", "CANONICAL", "GOLD", "SOURCE_OF_TRUTH", "CORRECTED"))]
    if marked:
        a = Anomaly(
            anomaly_id=uuid.uuid4().hex, anomaly_type="authority_markers", severity="high",
            message=f"{len(marked)} files claim authority (final/canonical/gold). Which governs?",
            object_ids=[r.object_id for r in marked],
            possible_answers=["Publication output", "Best candidate", "Authoritative source",
                              "Names unreliable", "Show examples"], blocking=True)
        # policy check: if a corpus authority policy exists, resolve it
        names = [r.name for r in marked]
        pol = next((p for p in store.policies if p.family == "authority"
                    and (not p.pattern or any(__import__("re").search(p.pattern, nm, 2) for nm in names))), None)
        if pol:
            a.blocking = False; a.resolved = True; a.ruling = pol.verdict
        anomalies.append(a)

    # organization question (the one that shapes the result) — non-blocking
    anomalies.append(Anomaly(
        anomaly_id=uuid.uuid4().hex, anomaly_type="organization", severity="low",
        message="How should the aggregated collection be organized?",
        possible_answers=["By meaningful category", "By extension",
                          "Series then format", "Flat root", "Show 3 candidates"],
        blocking=False))
    return anomalies


def _flat_name(rec: FileRecord, seen: dict) -> str:
    name = rec.name
    if name in seen:
        seen[name] += 1
        stem, ext = os.path.splitext(name)
        name = f"{stem}__{seen[name]}{ext}"
    else:
        seen[name] = 0
    return name


def _category(strategy: Strategy, rec: FileRecord) -> str:
    ext = rec.extension.lstrip(".").upper() or "NO_EXT"
    if strategy == Strategy.FLAT:
        return ""
    if strategy == Strategy.EXTENSION:
        return ext
    if strategy == Strategy.SERIES_THEN_FORMAT:
        return f"SERIES/{ext}"
    return rec.role or "_REVIEW"          # semantic (port: local-model category)


def _propose(job: FileJob, records: list[FileRecord], anomalies: list[Anomaly]) -> list[ProposedAction]:
    dest = Path(job.destination)
    blocking_ids = {oid for a in anomalies if a.blocking and not a.resolved for oid in a.object_ids}
    seen: dict[str, int] = {}
    seen_hashes: set[str] = set()
    op = Operation.MOVE if not job.preserve_originals else Operation.COPY
    actions = []
    for r in records:
        if r.role not in ("series_member", "possible_series_member"):
            continue
        if r.protected or r.object_id in blocking_ids:
            continue
        if job.exact_dedupe and r.sha256:
            if r.sha256 in seen_hashes:      # collapse exact dups inside the aggregate
                continue
            seen_hashes.add(r.sha256)
        cat = _category(job.strategy, r)
        fname = _flat_name(r, seen) if job.flatten else r.name
        target = dest / cat / fname
        r.proposed_path = str(target)
        actions.append(ProposedAction(
            action_id=uuid.uuid4().hex, operation=op, source=r.source_path,
            target=str(target), object_id=r.object_id, original_path=r.source_path,
            confidence=max(r.membership_score, r.ownership_prob)))
    return actions


def _authorize(job: FileJob, actions, anomalies) -> bool:
    if any(a.blocking and not a.resolved for a in anomalies):
        return False
    if not job.approved:
        return False
    for a in actions:
        a.authorized = True; a.state = State.APPROVED
    return True


def _execute(job: FileJob, actions) -> tuple[int, int]:
    if not (job.apply and job.approved):
        raise PermissionError("preview mode: apply and approved must both be true")
    done = fail = 0
    for a in actions:
        if not a.authorized:
            continue
        try:
            src, tgt = Path(a.source), Path(a.target)
            if tgt.exists():
                raise FileExistsError(tgt)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            if a.operation == Operation.COPY:
                shutil.copy2(src, tgt)
            elif a.operation == Operation.MOVE:
                shutil.move(str(src), str(tgt))
            a.state = State.EXECUTED; done += 1
        except Exception:
            a.state = State.FAILED; fail += 1
    return done, fail


def _verify(actions) -> list[str]:
    errors = []
    for a in actions:
        if a.state != State.EXECUTED:
            continue
        tgt = Path(a.target) if a.target else None
        if not tgt or not tgt.exists():
            errors.append(f"missing target: {a.target}"); continue
        if a.operation == Operation.COPY and _sha(Path(a.source)) != _sha(tgt):
            errors.append(f"hash mismatch: {a.target}")
    return errors


def _remember(result: JobResult):
    dest = Path(result.job.destination)
    dest.mkdir(parents=True, exist_ok=True)
    # rollback manifest (before/after for every executed action)
    rollback = [{"undo": "remove" if a.operation == Operation.COPY else "move_back",
                 "target": a.target, "original": a.original_path}
                for a in result.actions if a.state == State.EXECUTED]
    (dest / ".fis-rollback.json").write_text(json.dumps(rollback, indent=2), encoding="utf-8")
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "job": asdict(result.job),
             "records": len(result.records), "actions": len(result.actions),
             "executed": result.executed, "failed": result.failed,
             "anomalies": [asdict(a) for a in result.anomalies]}
    with (dest / ".fis-ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------- runner
def run_file_job(job: FileJob) -> JobResult:
    records = _find(job)
    _identify(records)
    _understand(job, records)
    _relate(job, records)
    _assign_roles(job, records)
    anomalies = _clarify(job, records)
    actions = _propose(job, records, anomalies)
    result = JobResult(job=job, records=records, anomalies=anomalies, actions=actions)

    if _authorize(job, actions, anomalies) and job.apply:
        result.executed, result.failed = _execute(job, actions)
        errs = _verify(actions)
        result.failed += len(errs)

    result.summary = _summary(records, anomalies, actions, job)
    _remember(result)
    return result


def _summary(records, anomalies, actions, job) -> dict:
    accepted = sum(1 for r in records if r.role == "series_member")
    review = sum(1 for r in records if r.role == "possible_series_member")
    excluded = sum(1 for r in records if r.role == "outside_collection")
    protected = sum(1 for r in records if r.protected)
    dup_groups = len({r.duplicate_group for r in records if r.duplicate_group})
    return {"candidates": accepted + review, "accepted": accepted, "need_ruling": review,
            "excluded": excluded, "protected_untouched": protected,
            "exact_duplicate_groups": dup_groups, "proposed_actions": len(actions),
            "originals_unchanged": job.preserve_originals, "mutations": 0 if not job.apply else None,
            "blocking_questions": sum(1 for a in anomalies if a.blocking and not a.resolved)}


# ---------------------------------------------------------------- GTQ recipe = a JobSpec
def gtq_job(roots: list[str], destination: str, **over) -> FileJob:
    spec = dict(job_id="JOB-GTQ-001", name="Aggregate Genesis to Quantum",
                roots=roots, destination=destination,
                operations=[Operation.SCAN, Operation.AGGREGATE, Operation.FLATTEN,
                            Operation.DEDUPLICATE, Operation.ORGANIZE, Operation.REPORT],
                strategy=Strategy.SERIES_THEN_FORMAT,
                aliases=["GTQ", "Genesis to Quantum", "Genesis-to-Quantum"],
                flatten=True, preserve_originals=True, apply=False, approved=False)
    spec.update(over)
    return FileJob(**spec)
