"""Lossless-only heuristics: exact SHA dups, token Jaccard near-dups, near-canon sidecar."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from fis_sidecar import read_existing

DUP_SOFT = 0.70
DUP_HARD = 0.80
WORD_RE = re.compile(r"[a-z0-9']{3,}")
TEXT_EXT = {".md", ".markdown", ".txt", ".html", ".htm", ".json"}
# 1–2 stages before canonical on the sidecar status ladder.
SIDECAR_LADDER = ("working", "draft", "watch", "review", "candidate", "reference", "canonical")
NEAR_CANON_STATUS = {"candidate", "reference"}
NEAR_CANON_STANDING = {"CANDIDATE", "OK"}


def sidecar_status(path: Path) -> str:
    existing = read_existing(path)
    canon = existing.get("canon") or {}
    return str(canon.get("status") or "").lower().strip()


def near_canon(path: Path, standing: str = "") -> bool:
    status = sidecar_status(path)
    if status in NEAR_CANON_STATUS:
        return True
    if standing.upper() in NEAR_CANON_STANDING:
        return True
    if status in SIDECAR_LADDER:
        gap = SIDECAR_LADDER.index("canonical") - SIDECAR_LADDER.index(status)
        return 1 <= gap <= 2
    return False


def word_set(path: Path) -> set[str]:
    if path.suffix.lower() not in TEXT_EXT:
        return set()
    try:
        if path.stat().st_size > 2_000_000:
            return set()
        text = path.read_text(encoding="utf-8", errors="ignore")[:80_000]
    except OSError:
        return set()
    return set(WORD_RE.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def folder_dup_report(files: list[Any]) -> dict[str, Any]:
    """files: sqlite rows with path, name, content_fingerprint."""
    sha_groups: dict[str, list[str]] = defaultdict(list)
    paths: list[tuple[str, Path]] = []
    for row in files:
        path = Path(row["path"])
        sha = row["content_fingerprint"] or ""
        if sha and not str(sha).endswith("-meta"):
            sha_groups[sha].append(row["name"])
        paths.append((row["name"], path))
    exact = [{"sha256": sha[:12], "files": names} for sha, names in sha_groups.items() if len(names) > 1]

    bags = [(name, path, word_set(path)) for name, path in paths]
    near: list[dict[str, Any]] = []
    pack_names: set[str] = set()
    for names in sha_groups.values():
        if len(names) > 1:
            pack_names.update(names)
    for i, (n1, p1, s1) in enumerate(bags):
        if near_canon(p1):
            pack_names.add(n1)
        if not s1:
            continue
        for n2, p2, s2 in bags[i + 1 :]:
            if not s2:
                continue
            if p1.suffix.lower() != p2.suffix.lower():
                continue
            score = jaccard(s1, s2)
            if score >= DUP_SOFT:
                band = "hard" if score >= DUP_HARD else "soft"
                near.append({
                    "a": n1,
                    "b": n2,
                    "jaccard": round(score, 3),
                    "band": band,
                })
                pack_names.add(n1)
                pack_names.add(n2)
    near.sort(key=lambda x: -x["jaccard"])
    return {
        "exact_groups": len(exact),
        "exact": exact,
        "near_pairs": near[:40],
        "near_soft_threshold": DUP_SOFT,
        "near_hard_threshold": DUP_HARD,
        "pack_names": sorted(pack_names),
        "semantic_state": "AVAILABLE" if near or exact else "NONE",
        "semantic_method": f"token Jaccard ≥ {int(DUP_SOFT*100)}% / {int(DUP_HARD*100)}% (SBERT later)",
    }


def semantic_html(record: Any, files: list[Any], children: list[Path], dups: dict[str, Any]) -> str:
    from html import escape
    name = escape(record["name"] if record else "")
    exact_n = dups.get("exact_groups") or 0
    near_n = len(dups.get("near_pairs") or [])
    packed = len(dups.get("pack_names") or [])
    near_rows = "".join(
        f"<tr><td>{escape(p['a'])}</td><td>{escape(p['b'])}</td>"
        f"<td>{p['jaccard']:.0%}</td><td>{escape(p['band'])}</td></tr>"
        for p in (dups.get("near_pairs") or [])[:12]
    ) or "<tr><td colspan='4' class='muted'>No token-overlap pairs at 70%+.</td></tr>"
    return f"""
<section id="semantic">
<h2>Semantic Capsule</h2>
<p class="section-note">Interpretive layer. Source files and hashes remain authoritative; this layer may be regenerated.</p>
<div class="top-grid">
  <div class="card">
    <h3>What this folder is</h3>
    <p><strong>{name} — lossless inventory. No rename, move, or delete.</strong></p>
    <div class="badges">
      <span class="badge">formal-system</span>
      <span class="badge">research-corpus</span>
      <span class="badge">heuristic-dups</span>
    </div>
    <div class="kv">
      <b>Current purpose</b><span>preserve source identity while exposing structure, drift, duplicates, and near-canon lossless packing</span>
      <b>Pack trigger</b><span>exact SHA dup, token overlap ≥70%/80%, or sidecar 1–2 stages before canonical (candidate/reference)</span>
      <b>Packed this folder</b><span>{packed} files queued for L0 packets</span>
    </div>
  </div>
  <div class="card" id="schema">
    <h3>Interpretation Schema</h3>
    <div class="kv">
      <b>Source layer</b><span>L0 exact bytes / SHA-256</span>
      <b>Structure layer</b><span>L1 deterministic extraction</span>
      <b>Claim layer</b><span>L2 claims / definitions / evidence</span>
      <b>Semantic layer</b><span>L3 compact index + capsule</span>
      <b>Corpus layer</b><span>L4 cross-document synthesis</span>
      <b>Recovery layer</b><span>L5 reconstruct originals from packets</span>
    </div>
  </div>
</div>
</section>
<section id="health">
<h2>Corpus Health</h2>
<div class="health-grid">
  <div class="health"><b>{len(files)}</b><span>Direct files</span></div>
  <div class="health"><b>{len(children)}</b><span>Child folders</span></div>
  <div class="health"><b>{exact_n}</b><span>Exact duplicate groups</span></div>
  <div class="health"><b>{near_n}</b><span>Near-dup pairs ≥70%</span></div>
</div>
</section>
<section id="relationships">
<h2>Relationships &amp; Rollup</h2>
<table class="signal-table">
<thead><tr><th>Relationship class</th><th>Current state</th><th>Method</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td>Exact duplicates</td><td>AVAILABLE</td><td>SHA-256</td><td>Byte-identical files, independent of filename.</td></tr>
<tr><td>Semantic duplicates</td><td>{escape(dups.get('semantic_state') or 'NONE')}</td><td>{escape(dups.get('semantic_method') or '')}</td><td>Different bytes, substantially the same words. SBERT remains a later layer.</td></tr>
<tr><td>Near-canon sidecar</td><td>AVAILABLE</td><td>candidate / reference</td><td>1–2 stages before canonical → lossless pack, not auto-promote.</td></tr>
</tbody>
</table>
<h3>Near-duplicate pairs</h3>
<table class="signal-table"><thead><tr><th>A</th><th>B</th><th>Overlap</th><th>Band</th></tr></thead><tbody>{near_rows}</tbody></table>
</section>
<section id="recovery">
<h2>Recovery Contract</h2>
<div class="card"><div class="kv">
  <b>Authoritative layer</b><span>original source bytes</span>
  <b>Identity proof</b><span>SHA-256</span>
  <b>Semantic capsule</b><span>derived and replaceable</span>
  <b>Rule</b><span>no semantic-layer change may alter or silently overwrite source identity</span>
</div></div>
</section>
"""
