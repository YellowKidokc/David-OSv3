#!/usr/bin/env python3
"""gate.py — pre-flight action gate.

Every file action (rename/move/archive/delete_later/...) is evaluated against the
rule stack BEFORE it runs: relevance -> guardrails -> folder profile -> action
conditions -> review-gate thresholds -> approval floor. The gate is never the final
authority: anything short of a hard safety stop returns ASK with the fired rules,
and the caller routes that to the user (approve once / always here / reject).

Pure stdlib. No I/O after construction. Decisions are plain JSON-shaped data so a
future Rust port can be differentially tested against this oracle (spec §8).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ALLOW, PREVIEW, ASK, BLOCK, DROP = "allow", "preview", "ask", "block", "drop"
_RANK = {ALLOW: 0, PREVIEW: 1, ASK: 2, BLOCK: 3}

MUTATING = {"rename", "move", "archive", "delete_later", "dedupe", "overwrite",
            "change_extension", "publish"}

SECRET_NAMES = {".env", ".env.local", ".env.production", ".env.development",
                "id_rsa", "id_ed25519", "id_dsa", "credentials.json", "key.txt"}
SECRET_SUFFIXES = (".pem", ".key", ".pfx", ".p12")
PROJECT_MARKERS = {"package.json", "pyproject.toml", "requirements.txt", "cargo.toml",
                   "pom.xml", "build.gradle", ".git", ".gitignore", "node_modules"}
SYSTEM_PREFIXES = ("c:\\windows", "c:\\program files", "c:\\program files (x86)",
                   "/c/windows", "/etc", "/usr", "/bin", "/sbin")

_RULE_JSONS = ("guardrails.v1.json", "actions_master.v1.json",
               "action_conditions.v1.json", "compatibility_matrix.v1.json",
               "review_gates.28pof.v1.json")


@dataclass
class Decision:
    verdict: str
    fired_rules: list[dict] = field(default_factory=list)   # [{"rule_id","reason"}]
    required_guardrails: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"verdict": self.verdict, "fired_rules": self.fired_rules,
                "required_guardrails": self.required_guardrails}


def _norm(p: str) -> str:
    return str(p).replace("/", "\\").lower()


def _is_system(p: str) -> bool:
    n = _norm(p)
    return any(n.startswith(s) for s in SYSTEM_PREFIXES)


def _is_secret(p: str) -> bool:
    name = Path(str(p)).name.lower()
    return name in SECRET_NAMES or name.endswith(SECRET_SUFFIXES)


def _is_project_file(p: str) -> bool:
    return Path(str(p)).name.lower() in PROJECT_MARKERS


def _threshold_number(text: str) -> tuple[str, float] | None:
    # ">20 files" -> (">", 20.0); "Any count" -> (">", 0.0)
    import re
    m = re.search(r"(>=|>)\s*(\d+)", text or "")
    if m:
        return m.group(1), float(m.group(2))
    if text and "any" in text.lower():
        return ">", 0.0
    return None


class Gate:
    def __init__(self, rules: dict, profile: dict, load_error: str | None = None):
        self.rules = rules
        self.profile = profile or {}
        self.load_error = load_error

    @classmethod
    def load(cls, rules_dir, profile) -> "Gate":
        rules: dict = {}
        try:
            for name in _RULE_JSONS:
                p = Path(rules_dir) / name
                rules[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            missing = [n for n in _RULE_JSONS if rules[n] is None]
            err = f"missing rule files: {', '.join(missing)}" if missing else None
        except (OSError, json.JSONDecodeError) as e:
            return cls({}, profile, load_error=f"rule load error: {e}")
        return cls(rules, profile, load_error=err)

    # -- individual checks, each returns Decision | None --------------------

    def _relevance(self, action_id: str) -> Decision | None:
        if action_id in self.profile.get("irrelevant_actions", ()):  # profile says N/A here
            return Decision(DROP, [{"rule_id": "profile.irrelevant_actions",
                                    "reason": f"{action_id} is not applicable in this folder"}])
        return None

    def _hard_safety(self, paths: list[str]) -> Decision | None:
        if any(_is_system(p) for p in paths):
            return Decision(BLOCK, [{"rule_id": "GR-001", "reason": "system folder — never touch"}],
                            ["GR-001"])
        if any(_is_secret(p) for p in paths):
            return Decision(BLOCK, [{"rule_id": "GR-004", "reason": "secrets/config file in batch"}],
                            ["GR-004"])
        return None

    def _guardrail_asks(self, action_id: str, paths: list[str], ctx: dict) -> Decision | None:
        fired = []
        if action_id in MUTATING and any(_is_project_file(p) for p in paths):
            fired.append({"rule_id": "GR-003", "reason": "project root marker in batch"})
        conf = ctx.get("confidence")
        if conf is not None and conf < float(ctx.get("review_threshold", 0.75)):
            fired.append({"rule_id": "GR-007",
                          "reason": f"confidence {conf:.2f} below review threshold"})
        if fired:
            return Decision(ASK, fired, [f["rule_id"] for f in fired])
        return None

    def _profile_rules(self, action_id: str) -> Decision | None:
        if action_id in self.profile.get("blocked_actions", ()):
            return Decision(ASK, [{"rule_id": "profile.blocked_actions",
                                   "reason": f"folder profile blocks '{action_id}' — user may override"}])
        return None

    def _action_conditions(self, action_id: str, ctx: dict) -> Decision | None:
        ac = (self.rules.get("action_conditions.v1.json") or {}).get("records", [])
        row = next((r for r in ac if r.get("action_id") == action_id), None)
        if not row:
            return None
        fired = []
        blocked_if = (row.get("blocked_if") or "").lower()
        if "protected" in blocked_if and ctx.get("protected"):
            fired.append({"rule_id": f"action_conditions:{action_id}",
                          "reason": "target is protected"})
        if "collision" in blocked_if and ctx.get("collision"):
            fired.append({"rule_id": f"action_conditions:{action_id}",
                          "reason": "filename collision"})
        if "project_root" in blocked_if and ctx.get("project_root"):
            fired.append({"rule_id": f"action_conditions:{action_id}",
                          "reason": "project root"})
        if fired:
            return Decision(ASK, fired)
        return None

    def _review_gates(self, action_id: str, ctx: dict) -> Decision | None:
        gates = (self.rules.get("review_gates.28pof.v1.json") or {}).get("records", [])
        trigger_key = {"rename": "rename_apply batch", "move": "route_apply batch",
                       "archive": "archive_apply batch", "delete_later": "delete candidate"}
        trig = trigger_key.get(action_id)
        if not trig:
            return None
        row = next((r for r in gates if r.get("trigger") == trig), None)
        if not row:
            return None
        tn = _threshold_number(row.get("default_threshold", ""))
        if tn and ctx.get("batch_size", 1) > tn[1]:
            return Decision(ASK, [{"rule_id": f"review_gate:{row.get('gate', trig)}",
                                   "reason": f"bulk {action_id}: batch {ctx.get('batch_size', 1)} "
                                             f"exceeds threshold '{row.get('default_threshold')}'"}])
        return None

    def _action_default_floor(self, action_id: str) -> str | None:
        ac = (self.rules.get("action_conditions.v1.json") or {}).get("records", [])
        row = next((r for r in ac if r.get("action_id") == action_id), None)
        return (row or {}).get("approval_default")

    def _approval_floor(self, action_id: str) -> Decision | None:
        # An explicit profile floor wins; without a profile the rulebook's own
        # per-action default is the floor, so unknown folders are never blind-allowed.
        floor = self.profile.get("approval_floor") or self._action_default_floor(action_id) or "preview_only"
        if action_id in MUTATING and floor == "blocked":
            return Decision(BLOCK, [{"rule_id": "profile.approval_floor",
                                     "reason": "profile declares this folder blocked for mutations"}])
        if action_id in MUTATING and floor == "approval_required":
            return Decision(ASK, [{"rule_id": "profile.approval_floor",
                                   "reason": f"approval required for mutations ({floor})"}])
        if action_id in MUTATING and floor in ("preview_only", "suggest_only"):
            return Decision(PREVIEW, [{"rule_id": "profile.approval_floor",
                                       "reason": f"profile floor is {floor}"}])
        # auto_after_threshold: the review-gate thresholds above ARE the threshold;
        # batches under them may proceed
        return None

    # -- the stack -----------------------------------------------------------

    def evaluate(self, action_id: str, target_paths, context: dict | None = None) -> Decision:
        ctx = dict(context or {})
        paths = [str(p) for p in target_paths]
        ctx.setdefault("batch_size", len(paths))
        ctx.setdefault("protected", bool(self.profile.get("protected")))

        if self.load_error:  # fail closed
            return Decision(ASK, [{"rule_id": "gate.load_error",
                                   "reason": f"load error: {self.load_error} — everything needs approval"}])

        if action_id not in MUTATING:
            return Decision(ALLOW)  # scan/hash/classify/report are always safe

        d = self._relevance(action_id)
        if d:
            return d
        d = self._hard_safety(paths)
        if d:
            return d  # BLOCK — never negotiable

        best = Decision(ALLOW)
        for check in (self._guardrail_asks(action_id, paths, ctx),
                      self._profile_rules(action_id),
                      self._action_conditions(action_id, ctx),
                      self._review_gates(action_id, ctx),
                      self._approval_floor(action_id)):
            if check is None:
                continue
            if _RANK[check.verdict] > _RANK[best.verdict]:
                best = Decision(check.verdict, [], [])
            if check.verdict == best.verdict:
                best.fired_rules.extend(check.fired_rules)
                best.required_guardrails.extend(check.required_guardrails)
        return best
