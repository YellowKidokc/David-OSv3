"""Govern (gov) — emit the .fisnote v2 (the node).

A node carries: identity · meaning · permission · memory (event ledger) ·
agency (a DECLARATIVE capability manifest — never embedded code).

By default written to the output dir, NOT into your folders. --in-place is opt-in.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .model import Atlas, FolderRecord, ObjectRecord


def _iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def render_corpus_root(f: FolderRecord, territories: list[FolderRecord]) -> str:
    """The constitution + territory map. Does NOT enumerate files."""
    front = {
        "fisnote_version": "2.0",
        "node": {"node_id": f.node_id, "node_type": "corpus_root",
                 "display_name": f.name, "purpose": f.purpose},
        "identity": {"path": f.full_path, "authority_status": "user_confirmation_required"},
        "inventory": {"total_folders": len(territories) + 1,
                      "direct_child_folders": f.direct_children,
                      "total_descendants": f.total_descendants,
                      "total_bytes": f.total_size},
        "meaning": {"folder_class": "research_corpus", "importance": "critical",
                    "lifecycle_state": "active"},
        "authority": {"source_of_truth": "unresolved", "canonicality_is_local": True,
                      "rule": "The root is not itself canonical; authority is assigned to child territories/files.",
                      "canonical_marker_warning": "Filenames are evidence of intended status, not proof."},
        "permissions": f.permissions,
        "automation": {"mutating_automation_enabled": False, "action_mode": "report_only",
                       "on_change": ["inspect/inventory_refresh", "inspect/staleness_check", "govern/ledger_event"],
                       "on_new_file": ["inspect/type_detect", "understand/classify", "govern/risk_score"]},
        "confidence": {"classification_review_below": 0.75, "suggestion_threshold": 0.90,
                       "authority_never_inferred_from_confidence": True},
        "open_questions": f.open_questions,
    }
    lines = ["---", json.dumps(front, indent=2, ensure_ascii=False)[1:-1].rstrip(), "---\n"]
    lines.append(f"# FIS Corpus Root: {f.name}")
    lines.append(f"**{f.purpose}**\n")
    lines.append("> This root is the **constitution + map**. It does not list files. "
                 "Each territory's own `.fisnote` describes its contents.\n")
    lines.append("## Territory map (preliminary inferences — need user ruling)")
    lines.append("| Territory | Inferred class | Risk | Ordering | Treatment |")
    lines.append("|---|---|---|---|---|")
    for t in sorted(territories, key=lambda x: x.name.lower()):
        icon = {"red": "🔴", "amber": "🟡", "green": "🟢"}.get(t.risk, "")
        order = "numbered seq" if t.ordering_scheme else "—"
        treat = "preserve intact; no auto path changes" if t.risk != "green" else "may propose after preview"
        lines.append(f"| `{t.name}` | {t.folder_class} | {icon} {t.risk} | {order} | {treat} |")
    if f.canonical_candidates:
        lines.append(f"\n## Canonical/gold claims found ({len(f.canonical_candidates)}) — claims, not proof")
        for c in f.canonical_candidates[:20]:
            lines.append(f"- `{c}`")
    lines.append("\n## Open questions (must be resolved before any reorganization)")
    for q in f.open_questions:
        lines.append(f"- [ ] {q}")
    lines.append("\n<!-- fisnote.v2 corpus_root — report-only until canon hierarchy resolved. -->")
    return "\n".join(lines)


def render_fisnote(f: FolderRecord, children: list[ObjectRecord]) -> str:
    risk_icon = {"red": "🔴", "amber": "🟡", "green": "🟢"}.get(f.risk, "⚪")
    front = {
        "fis_schema": "fisnote.v2",
        "op": "gov",
        "folder": f.name,
        "path": f.full_path,
        "generated_at": _iso(),
        "purpose": f.purpose,
        "folder_class": f.folder_class,
        "class_confidence": round(f.class_confidence, 2),
        "class_evidence": f.evidence.reasons,
        "risk": f.risk,
        "red_flags": f.red_flags,
        "allowed_actions": f.allowed_actions,
        "forbidden_actions": f.forbidden_actions,
        "behaves_like": f.behaves_like,
        "direct_children": f.direct_children,
        "total_descendants": f.total_descendants,
        "total_size": f.total_size,
        "type_distribution": f.type_distribution,
        "move_breaks_relationships": f.move_breaks_relationships,
        # DECLARATIVE agency — a request, never code.
        "node": {
            "watch": False,
            "on_new_file": ["und/classify", "dec/normalize_name"],
            "notify": {"when": "new_file", "channel": "toast"},
        },
    }
    lines = ["---"]
    lines.append(json.dumps(front, indent=2, ensure_ascii=False)[1:-1].rstrip())
    lines.append("---\n")
    lines.append(f"# FIS Node: {f.name}")
    lines.append(f"**What this is:** {f.purpose}")
    lines.append(f"**Type:** {f.folder_class} · **Risk:** {risk_icon} {f.risk} · "
                 f"**You may:** {', '.join(f.allowed_actions) or '—'}")
    if f.forbidden_actions:
        lines.append(f"**Never:** {', '.join(f.forbidden_actions)}")
    lines.append("\n## Direct files (description · role · activity · event ledger)")
    for o in sorted(children, key=lambda x: x.name.lower()):
        lines.append(
            f"- `{o.name}` :: {o.content_type} · {o.detected_role} · {o.activity} "
            f"· sens={o.sensitivity} · treat={o.proposed_treatment} "
            f"(class {o.class_confidence:.2f}/act {o.action_confidence:.2f})"
        )
        lines.append(f"    - events: created … modified … opened … moved=not_moved")
    lines.append("\n<!-- fisnote.v2 — parseable, safe to regenerate. -->")
    return "\n".join(lines)


def emit_all(atlas: Atlas, out_dir: Path, in_place: bool = False) -> list[Path]:
    # best-effort operational-language capsule (needs the registry + PyYAML)
    reg = None
    try:
        from . import registry as _reg
        reg = _reg.load()
    except Exception:
        reg = None

    written = []
    root_path = atlas.root
    for f in atlas.folders.values():
        if f.node_type == "corpus_root":
            territories = [g for g in atlas.folders.values()
                           if g.parent_node == f.node_id and g.node_type == "research_territory"]
            note = render_corpus_root(f, territories)
        else:
            children = [o for o in atlas.objects.values() if o.parent == f.full_path]
            note = render_fisnote(f, children)
        if reg is not None:
            try:
                cap = _reg.folder_capsule(reg, f.object_id, f.risk)
                note += (f"\n\n<!-- FIS capsule {cap} :: {reg.decompress(cap)} -->")
            except Exception:
                pass
        if in_place:
            target = Path(f.full_path) / ".fisnote"
        else:
            safe = f.rel_path.replace("\\", "__").replace("/", "__") or "_root"
            target = out_dir / "fisnotes" / f"{safe}.fisnote.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(note, encoding="utf-8")
        written.append(target)
    return written
