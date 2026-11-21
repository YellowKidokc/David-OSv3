#!/usr/bin/env python3
"""Create the organize.db SQLite database with schema."""
import os, sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "organize.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS drives (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'unknown',
    label TEXT DEFAULT '',
    is_source INTEGER DEFAULT 1,
    is_target INTEGER DEFAULT 0,
    last_scanned TEXT,
    created TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    drive_id INTEGER REFERENCES drives(id),
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    ext TEXT DEFAULT '',
    size INTEGER DEFAULT 0,
    modified REAL,
    hash_head TEXT DEFAULT '',
    detected_role TEXT DEFAULT '',
    markers TEXT DEFAULT '',
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    UNIQUE(drive_id, path, name)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    drive_id INTEGER REFERENCES drives(id),
    scanned_at TEXT DEFAULT (datetime('now')),
    total_files INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    duration_sec REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    batch_id TEXT,
    action TEXT NOT NULL,
    src_path TEXT,
    dst_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    risk TEXT DEFAULT 'green',
    status TEXT DEFAULT 'pending',
    executed_at TEXT,
    created TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    risk TEXT DEFAULT 'green',
    action_type TEXT DEFAULT 'copy',
    from_role TEXT,
    to_role TEXT,
    reason TEXT,
    item_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'proposed',
    created TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_drive ON files(drive_id);
CREATE INDEX IF NOT EXISTS idx_files_ext ON files(ext);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash_head);
CREATE INDEX IF NOT EXISTS idx_files_role ON files(detected_role);
CREATE INDEX IF NOT EXISTS idx_actions_batch ON actions(batch_id);
"""

ROLE_MARKERS = {
    "repo":        [".git"],
    "obsidian":    [".obsidian"],
    "node_project":["package.json", "node_modules"],
    "python_project":["pyproject.toml", "setup.py", "requirements.txt"],
    "rust_project":["Cargo.toml"],
    "theophysics": ["faiththruphysics", "theophysics", "LOGOS", "MDA"],
    "html_output": [],  # detected by extension ratio
    "lean_project":["lakefile.lean", "lean-toolchain"],
}

def detect_role(dirpath, filenames, dirnames):
    """Detect what role a folder plays based on marker files."""
    roles = []
    names_lower = [f.lower() for f in filenames]
    dirs_lower = [d.lower() for d in dirnames]
    all_items = names_lower + dirs_lower
    path_lower = dirpath.lower()

    if ".git" in dirs_lower:
        roles.append("repo")
    if ".obsidian" in dirs_lower:
        roles.append("obsidian")
    if "package.json" in names_lower:
        roles.append("node_project")
    if any(f in names_lower for f in ["pyproject.toml", "setup.py", "requirements.txt"]):
        roles.append("python_project")
    if "cargo.toml" in names_lower:
        roles.append("rust_project")
    if any(f in names_lower for f in ["lakefile.lean", "lean-toolchain"]):
        roles.append("lean_project")
    if any(t in path_lower for t in ["faiththruphysics", "theophysics", "logos_v", "mda-build", "genesis_to_quantum", "gtq"]):
        roles.append("theophysics")

    # HTML-heavy detection
    html_count = sum(1 for f in names_lower if f.endswith((".html", ".htm")))
    if html_count >= 5 and len(filenames) > 0 and html_count / len(filenames) > 0.5:
        roles.append("html_output")

    return ",".join(roles) if roles else ""


def scan_to_db(folder_path, role="unknown", label="", is_source=True, is_target=False):
    """Scan a folder and write all files to the database."""
    import hashlib, time

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    # Upsert drive
    c.execute("INSERT INTO drives (path, role, label, is_source, is_target) VALUES (?, ?, ?, ?, ?) "
              "ON CONFLICT(path) DO UPDATE SET role=?, label=?, is_source=?, is_target=?, last_scanned=datetime('now')",
              (folder_path, role, label, int(is_source), int(is_target), role, label, int(is_source), int(is_target)))
    drive_id = c.execute("SELECT id FROM drives WHERE path=?", (folder_path,)).fetchone()[0]

    start = time.time()
    total_files = 0
    total_size = 0

    for dirpath, dirnames, filenames in os.walk(folder_path):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") or d in (".git", ".obsidian")]

        folder_role = detect_role(dirpath, filenames, dirnames)

        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                sz = os.path.getsize(fp)
                mt = os.path.getmtime(fp)
            except:
                continue

            ext = os.path.splitext(fname)[1].lower()

            # Hash first 64KB for dedup
            hash_head = ""
            if sz > 0:
                try:
                    h = hashlib.md5()
                    with open(fp, "rb") as fh:
                        h.update(fh.read(65536))
                    hash_head = h.hexdigest()
                except:
                    pass

            c.execute("""INSERT INTO files (drive_id, path, name, ext, size, modified, hash_head, detected_role, markers, last_seen)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                         ON CONFLICT(drive_id, path, name) DO UPDATE SET
                         size=?, modified=?, hash_head=?, detected_role=?, last_seen=datetime('now')""",
                      (drive_id, dirpath, fname, ext, sz, mt, hash_head, folder_role, "",
                       sz, mt, hash_head, folder_role))

            total_files += 1
            total_size += sz

    elapsed = time.time() - start

    c.execute("INSERT INTO snapshots (drive_id, total_files, total_size, duration_sec) VALUES (?, ?, ?, ?)",
              (drive_id, total_files, total_size, elapsed))

    db.commit()
    db.close()

    return {"drive_id": drive_id, "files": total_files, "size": total_size, "seconds": round(elapsed, 2)}


def reconcile():
    """Compare all source drives against target drives and generate action batches."""
    import uuid

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    sources = c.execute("SELECT * FROM drives WHERE is_source=1").fetchall()
    targets = c.execute("SELECT * FROM drives WHERE is_target=1").fetchall()

    if not sources or not targets:
        db.close()
        return {"error": "Need at least one source and one target drive. Add drives first."}

    # Build target file index: hash -> [(path, name, drive_role)]
    target_hashes = {}
    target_names = {}
    for t in targets:
        rows = c.execute("SELECT path, name, hash_head, size FROM files WHERE drive_id=?", (t["id"],)).fetchall()
        for r in rows:
            if r["hash_head"]:
                target_hashes.setdefault(r["hash_head"], []).append({"path": r["path"], "name": r["name"], "target": t["path"], "role": t["role"]})
            target_names.setdefault(r["name"], []).append({"path": r["path"], "hash": r["hash_head"], "size": r["size"], "target": t["path"], "role": t["role"]})

    # Clear old proposed batches
    c.execute("DELETE FROM batches WHERE status='proposed'")
    c.execute("DELETE FROM actions WHERE status='pending'")

    batches_out = []

    for src in sources:
        src_files = c.execute("SELECT path, name, ext, size, hash_head, detected_role FROM files WHERE drive_id=?", (src["id"],)).fetchall()

        missing = []
        identical = []
        conflicts = []

        for f in src_files:
            full_path = os.path.join(f["path"], f["name"])

            if f["hash_head"] and f["hash_head"] in target_hashes:
                identical.append(f)
            elif f["name"] in target_names:
                # Same name, different content
                conflicts.append(f)
            else:
                missing.append(f)

        # Find best target for missing files based on role matching
        role_map = {}
        for m in missing:
            role = m["detected_role"].split(",")[0] if m["detected_role"] else ""
            role_map.setdefault(role, []).append(m)

        for role, files in role_map.items():
            # Find matching target
            best_target = None
            for t in targets:
                if role and role in t["role"]:
                    best_target = t
                    break
            if not best_target and targets:
                best_target = targets[0]  # fallback to first target

            if not best_target:
                continue

            batch_id = str(uuid.uuid4())[:8]
            risk = "green"
            label_role = role if role else "general"
            label = f"Copy {len(files)} {label_role} files from {src['label'] or src['path']} to {best_target['label'] or best_target['path']}"

            c.execute("INSERT INTO batches (id, label, risk, action_type, from_role, to_role, reason, item_count) VALUES (?,?,?,?,?,?,?,?)",
                      (batch_id, label, risk, "copy", src["role"], best_target["role"],
                       f"Files detected as '{label_role}' missing from target", len(files)))

            for f in files:
                c.execute("INSERT INTO actions (batch_id, action, src_path, dst_path, file_name, file_size, risk) VALUES (?,?,?,?,?,?,?)",
                          (batch_id, "copy", os.path.join(f["path"], f["name"]), best_target["path"], f["name"], f["size"], risk))

            batches_out.append({"id": batch_id, "label": label, "risk": risk, "count": len(files)})

        # Conflict batch
        if conflicts:
            batch_id = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO batches (id, label, risk, action_type, from_role, to_role, reason, item_count) VALUES (?,?,?,?,?,?,?,?)",
                      (batch_id, f"Review {len(conflicts)} conflicts from {src['label'] or src['path']}", "yellow", "review",
                       src["role"], "", "Same filename exists in target but content differs", len(conflicts)))
            for f in conflicts:
                c.execute("INSERT INTO actions (batch_id, action, src_path, file_name, file_size, risk) VALUES (?,?,?,?,?,?)",
                          (batch_id, "review", os.path.join(f["path"], f["name"]), f["name"], f["size"], "yellow"))
            batches_out.append({"id": batch_id, "label": f"Review {len(conflicts)} conflicts", "risk": "yellow", "count": len(conflicts)})

        # Identical summary
        if identical:
            batches_out.append({"id": "info", "label": f"{len(identical)} files from {src['label'] or src['path']} already exist in targets (identical hash)", "risk": "info", "count": len(identical)})

    db.commit()
    db.close()

    return {"batches": batches_out, "total_batches": len(batches_out)}


if __name__ == "__main__":
    import sys

    # Create DB
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.commit()
    db.close()
    print(f"Database ready: {DB_PATH}")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "scan" and len(sys.argv) >= 3:
            path = sys.argv[2]
            role = sys.argv[3] if len(sys.argv) > 3 else "unknown"
            label = sys.argv[4] if len(sys.argv) > 4 else ""
            is_target = "--target" in sys.argv
            result = scan_to_db(path, role=role, label=label, is_source=not is_target, is_target=is_target)
            print(f"Scanned: {result['files']} files, {result['size']} bytes in {result['seconds']}s")
        elif cmd == "reconcile":
            result = reconcile()
            import json
            print(json.dumps(result, indent=2))
        elif cmd == "status":
            db = sqlite3.connect(DB_PATH)
            drives = db.execute("SELECT path, role, label, is_source, is_target, last_scanned FROM drives").fetchall()
            total = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            print(f"Drives: {len(drives)}, Total files indexed: {total}")
            for d in drives:
                tag = "SOURCE" if d[3] else "TARGET"
                print(f"  [{tag}] {d[0]} role={d[1]} label={d[2]} scanned={d[5]}")
            db.close()
    else:
        print("Usage:")
        print("  python engine.py                          # create/verify DB")
        print("  python engine.py scan D:\\GitHub repo dev  # scan source")
        print("  python engine.py scan \\\\NAS\\GitHub repo archive --target  # scan target")
        print("  python engine.py reconcile                # generate action batches")
        print("  python engine.py status                   # show indexed drives")
