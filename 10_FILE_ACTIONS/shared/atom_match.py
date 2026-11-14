"""atom_match.py — Match documents by shared claim atoms via the ATOM pipeline.

Architecture:
  1. deep_identify finds files, classifies them, discovers families (structural layer)
  2. For papers and high-confidence documents, run the atoms station to extract claims
  3. Match papers by shared atoms — two papers with 3+ shared claims are structurally related
     even with different names, different folders, different authors

This module bridges deep_identify's scan_db to the Faith-through-physics-atoms pipeline.

Usage:
    from atom_match import AtomMatcher
    matcher = AtomMatcher(scan_db, atoms_repo_path)
    matcher.extract_atoms(paths, provider="deepseek")  # run atoms station on selected files
    matches = matcher.find_matches(min_shared=2)        # find papers that share claims
    matcher.merge_into_families(matches)                # update families in scan_db
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

ATOMS_REPO = Path(r"D:\GitHub\Faith-through-physics-atoms")


class AtomMatcher:
    def __init__(self, scan_db, atoms_repo: Path = ATOMS_REPO):
        self.db = scan_db
        self.repo = atoms_repo
        self._ensure_tables()

    def _ensure_tables(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS atom_extractions (
            path TEXT NOT NULL,
            scan_id TEXT,
            run_uuid TEXT NOT NULL,
            provider TEXT,
            atom_count INTEGER,
            atoms_json TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (path, run_uuid)
        );
        CREATE TABLE IF NOT EXISTS atom_matches (
            path_a TEXT NOT NULL,
            path_b TEXT NOT NULL,
            shared_atoms INTEGER,
            shared_atom_ids TEXT,
            confidence REAL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (path_a, path_b)
        );
        CREATE INDEX IF NOT EXISTS ix_atom_path ON atom_extractions(path);
        CREATE INDEX IF NOT EXISTS ix_match_a ON atom_matches(path_a);
        CREATE INDEX IF NOT EXISTS ix_match_b ON atom_matches(path_b);
        """)
        self.db.conn.commit()

    async def extract_atoms_for_file(self, path: str, provider: str = "deepseek") -> dict:
        """Run the atoms station on a single file. Returns the extraction result."""
        import os, sys
        # Ensure API key is available
        if not os.environ.get("DEEPSEEK_API_KEY"):
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                    os.environ["DEEPSEEK_API_KEY"] = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")[0]
            except Exception:
                return {"path": path, "error": "DEEPSEEK_API_KEY not set", "atom_count": 0, "atoms": []}
        old_cwd = os.getcwd()
        os.chdir(str(self.repo))
        sys.path.insert(0, str(self.repo))
        from api_client.completion import complete
        from canon_store.prompts import load_prompt
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")[:32000]
            system = load_prompt("atoms", "extract-claims")
            user = f"PAPER TITLE: {Path(path).stem}\n\nSOURCE TEXT:\n{text}"

            run_id = uuid.uuid4().hex[:12]
            result, receipt = await complete(
                provider=provider,
                system=system,
                user=user,
                json_mode=True,
                run_uuid=run_id,
            )

            atoms = []
            if isinstance(result, dict):
                atoms = result.get("claims", result.get("atoms", []))
            elif isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    atoms = parsed.get("claims", parsed.get("atoms", []))
                except json.JSONDecodeError:
                    atoms = []

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            scan = self.db.latest_scan()
            scan_id = scan["scan_id"] if scan else ""

            self.db.conn.execute(
                "INSERT OR REPLACE INTO atom_extractions VALUES (?,?,?,?,?,?,?)",
                (path, scan_id, run_id, provider, len(atoms),
                 json.dumps(atoms, ensure_ascii=False), now))
            self.db.conn.commit()

            return {"path": path, "run_uuid": run_id, "atom_count": len(atoms), "atoms": atoms}
        finally:
            os.chdir(old_cwd)

    async def extract_atoms_batch(self, paths: list[str], provider: str = "deepseek",
                                   max_concurrent: int = 10) -> list[dict]:
        """Extract atoms for multiple files with bounded concurrency."""
        sem = asyncio.Semaphore(max_concurrent)
        async def _limited(p):
            async with sem:
                try:
                    return await self.extract_atoms_for_file(p, provider)
                except Exception as e:
                    return {"path": p, "error": str(e), "atom_count": 0, "atoms": []}
        return await asyncio.gather(*[_limited(p) for p in paths])

    def find_matches(self, min_shared: int = 2) -> list[dict]:
        """Find pairs of documents that share claim atoms."""
        rows = self.db.conn.execute(
            "SELECT path, atoms_json FROM atom_extractions WHERE atom_count > 0"
        ).fetchall()

        # Build atom -> document index
        # Atoms come back as nested objects with discovery.claim_text or admission.natural_language_summary
        # or as flat strings. Normalize to the actual claim text for matching.
        doc_atoms: dict[str, set[str]] = {}
        for row in rows:
            atoms = json.loads(row["atoms_json"])
            atom_ids = set()
            for a in atoms:
                text = ""
                if isinstance(a, dict):
                    # Try nested paths first (the actual atom format)
                    text = (a.get("discovery", {}).get("claim_text", "")
                            or a.get("admission", {}).get("natural_language_summary", "")
                            or a.get("discovery", {}).get("formal_statement", "")
                            or a.get("claim", "")
                            or a.get("text", "")
                            or a.get("atom", "")
                            or str(a.get("identity", {}).get("content_hash", "")))
                elif isinstance(a, str):
                    text = a
                if text:
                    # Normalize: lowercase, first 100 chars, hash for stable ID
                    norm = text.strip().lower()[:100]
                    aid = hashlib.sha1(norm.encode()).hexdigest()[:10]
                    atom_ids.add(aid)
            if atom_ids:
                doc_atoms[row["path"]] = atom_ids

        # Find overlaps
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        matches = []
        paths = sorted(doc_atoms.keys())
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                shared = doc_atoms[paths[i]] & doc_atoms[paths[j]]
                if len(shared) >= min_shared:
                    conf = min(len(shared) / 5.0, 1.0)  # 5+ shared atoms = full confidence
                    match = {
                        "path_a": paths[i], "path_b": paths[j],
                        "shared_atoms": len(shared),
                        "shared_atom_ids": sorted(shared),
                        "confidence": round(conf, 4),
                    }
                    matches.append(match)
                    self.db.conn.execute(
                        "INSERT OR REPLACE INTO atom_matches VALUES (?,?,?,?,?,?)",
                        (paths[i], paths[j], len(shared),
                         json.dumps(sorted(shared)), conf, now))
        self.db.conn.commit()
        matches.sort(key=lambda m: -m["shared_atoms"])
        return matches

    def select_for_extraction(self, doc_type: str = "paper", min_confidence: float = 0.4,
                               limit: int = 30) -> list[str]:
        """Pick documents worth running through the atoms station."""
        scan = self.db.latest_scan()
        if not scan:
            return []
        rows = self.db.conn.execute(
            """SELECT c.path FROM cards c
               LEFT JOIN atom_extractions a ON c.path = a.path
               WHERE c.scan_id = ? AND c.doc_type = ? AND c.identity_confidence >= ?
                 AND a.path IS NULL AND c.extraction_status = 'read'
               ORDER BY c.identity_confidence DESC LIMIT ?""",
            (scan["scan_id"], doc_type, min_confidence, limit)
        ).fetchall()
        return [r["path"] for r in rows]

    def stats(self) -> dict:
        extracted = self.db.conn.execute("SELECT COUNT(*) FROM atom_extractions").fetchone()[0]
        total_atoms = self.db.conn.execute(
            "SELECT COALESCE(SUM(atom_count),0) FROM atom_extractions").fetchone()[0]
        matches = self.db.conn.execute("SELECT COUNT(*) FROM atom_matches").fetchone()[0]
        return {"documents_extracted": extracted, "total_atoms": total_atoms, "matches_found": matches}
