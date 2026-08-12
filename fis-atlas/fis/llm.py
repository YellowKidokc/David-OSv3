"""Small local LLM seam (und) — question WORDING only, via Ollama.

Constrained to one job: pick a question template and fill variables. It must
NOT invent filesystem policy (that stays deterministic/governed). If Ollama is
not installed/reachable, everything degrades to the deterministic template — the
system never depends on the model being present.

Recommended small models (open source, on-device):
  qwen2.5:0.5b   · smollm2:1.7b   · gemma3:1b
Pull once:  ollama pull qwen2.5:0.5b
"""
from __future__ import annotations

import json
import urllib.request

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:0.5b"

# ── The model capability contract (David's rule: it must know STRICTLY what it
# can and cannot do). Enforced, not documentation. ────────────────────────────
MODEL_CAN = {
    "select_question_template",
    "fill_template_variables",
    "phrase_question",
    "explain_evidence_plainly",
    "summarize_findings",
    "interpret_free_text_answer",
    "propose_rule_from_ruling",     # PROPOSE only — a human ruling still admits it
}
MODEL_CANNOT = {
    "invent_policy", "decide_authority", "promote_canonical", "admit_bridge",
    "set_standing", "change_permissions", "override_guardrail",
    "execute_action", "move_file", "rename_file", "delete_file", "archive_file",
}


class CapabilityError(PermissionError):
    pass


def enforce(capability: str) -> None:
    """Deny any capability outside the allow-list. Fail closed on unknowns."""
    if capability in MODEL_CANNOT or capability not in MODEL_CAN:
        raise CapabilityError(
            f"model is not permitted to '{capability}'. Allowed: {sorted(MODEL_CAN)}")


def available(timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


class OllamaQuestioner:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def select_template(self, anomaly: str, evidence: list[str],
                        allowed_templates: list[str]) -> dict | None:
        """Return {template, variables} or None if the model is unavailable/unsure.

        The caller treats None as 'use the deterministic template'.
        """
        enforce("select_question_template")     # contract check, fail-closed
        if not available():
            return None
        prompt = (
            "You select a question template. Do NOT invent policy. "
            "Return strict JSON {\"template\": <one of allowed>, \"variables\": {...}}.\n"
            f"anomaly: {anomaly}\nevidence: {json.dumps(evidence[:8])}\n"
            f"allowed_templates: {json.dumps(allowed_templates)}\n"
        )
        try:
            body = json.dumps({"model": self.model, "prompt": prompt,
                               "stream": False, "format": "json",
                               "options": {"temperature": 0}}).encode()
            req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.loads(r.read())
            parsed = json.loads(out.get("response", "{}"))
            # reject any attempt to smuggle an action/policy past the contract
            if any(k in parsed for k in ("action", "policy", "execute", "command", "authority")):
                return None
            tmpl = parsed.get("template")
            if tmpl in allowed_templates:
                return {"template": tmpl, "variables": parsed.get("variables", {})}
        except Exception:
            return None
        return None


def phrase_question(deterministic_text: str, anomaly: str, evidence: list[str],
                    allowed_templates: list[str], questioner: OllamaQuestioner | None = None) -> dict:
    """Deterministic-first: always have a valid question; let the LLM refine only if present."""
    result = {"text": deterministic_text, "template": None, "source": "deterministic"}
    q = questioner or OllamaQuestioner()
    picked = q.select_template(anomaly, evidence, allowed_templates)
    if picked:
        result.update(template=picked["template"], variables=picked.get("variables", {}),
                      source="ollama")
    return result
