"""structural_evidence.py — Structural Evidence Profile v2.

Engine version: structural-evidence-v2
Evaluates evidence-bearing structure across 4 independent channels (0-25 each, capped at 25, composite max 100):
  1. data_channel: Structured observations, empirical datasets, quantitative tables, measurements.
     (Metadata configs are cataloged as metadata, not empirical observations).
  2. math_channel: Display equations, operational variables (chi, sigma, S_eff), step-by-step derivations.
  3. formal_channel: Lean 4 theorems, formal logic syntax, algorithmic code.
     (Flags proof gaps: sorry, admit, ungrounded axioms).
  4. falsification_channel: Kill conditions, concrete testable predictions, negative controls, receipts.
     (Authority does not transfer truth: citations/links earn zero automatic rigor points).

Diminishing returns apply to repeated artifacts.
"""

from __future__ import annotations

import re
import json
from typing import Any, Dict, List, Tuple

VERSION = "structural-evidence-v2"

# ── Math patterns ────────────────────────────────────────────────────────────
DISPLAY_MATH_RE = re.compile(r"(\$\$.+?\$\$|\\\[.+?\\\]|\\begin\{equation\}.+?\\end\{equation\})", re.DOTALL)
INLINE_MATH_RE  = re.compile(r"(?<!\$)\$(?!\$)[^$\n]+?\$(?!\$)|\\\([^\n]+?\\\)")
MATH_OPERATORS_RE = re.compile(r"[\u03c7\u03c3\u03b7\u03bb\u0127\u2207\u2202\u222b\u222c\u222d\u2211\u220f\u2264\u2265\u2260\u2248\u221d]|\b(chi|sigma|S_eff|S_prod|hbar|nabla|partial|integral|sum)\b", re.IGNORECASE)
DERIVATION_STEP_RE = re.compile(r"\b(step\s+\d+|derives?\s+from|integrating\s+over|yields|substituting|by\s+definition|therefore|hence|\u2234)\b", re.IGNORECASE)

# ── Formal Logic & Lean patterns ─────────────────────────────────────────────
LEAN_THEOREMS_RE = re.compile(r"\b(theorem|def|lemma|structure|inductive|class)\s+([a-zA-Z0-9_']+)", re.MULTILINE)
LEAN_BUILD_RECEIPT_RE = re.compile(r"\b(LEAN[\s_-]?VERIFIED|lake\s+build\s+passed|QED|rfl|exact\s+[a-zA-Z0-9_']+)\b")
LEAN_GAP_RE = re.compile(r"\b(sorry|admit|axiom\s+[a-zA-Z0-9_']+|\bWIP\b|TODO\s+proof)\b")
FORMAL_LOGIC_RE = re.compile(r"[\u2200\u2203\u22a2\u22a8\u21d2\u21d4\u2227\u2228\u00ac\u22a4\u22a5]|\b(forall|exists|proves|entails|iff|negation)\b")
CODE_BLOCK_RE = re.compile(r"```([a-zA-Z0-9_-]*)\n(.*?)```", re.DOTALL)

# ── Data & Observations patterns ─────────────────────────────────────────────
MD_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
MD_TABLE_DIVIDER_RE = re.compile(r"^\s*\|[- :|]+\|\s*$", re.MULTILINE)
HTML_TABLE_RE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)
NUMERIC_MEASURE_RE = re.compile(r"\b(\d+(?:\.\d+)?%|N\s*=\s*\d+|p\s*[<>=]\s*0?\.\d+|\d+(?:\.\d+)?\s*(?:eV|GeV|TeV|Hz|kHz|MHz|GHz|kg|ms|s|K|m/s|bps|bits|qubits|sigma))\b")

# ── Falsification & Receipts patterns ────────────────────────────────────────
KILL_CONDITION_RE = re.compile(
    r"(?im)(?:^\s*(?:kill[\s_-]*condition|falsif(?:ier|iable|ication)|disproved\s+if|fail(?:ure)?[\s_-]*condition)\s*[:\-]?\s*(.+)$|##+\s*.*falsification\s+criteria|\bsurvives\s+or\s+falls\s+on\s+testable\s+claims\b|\bif\s+no\s+such\s+parallels\s+exist\b|\bmerely\s+a\s+metaphor\b)"
)
PREDICTION_RE = re.compile(
    r"(?im)(?:^\s*(?:prediction|testable\s+prediction|concrete\s+prediction|observable\s+forecast)\s*[:\-]?\s*(.+)$|:::\s*\{[^}]*\}\s*(?:Claim\s+\d+|Hypothesis\s+\d+)|\b(?:Claim|Hypothesis)\s+[1-9]\b)"
)
NEGATIVE_CONTROL_RE = re.compile(
    r"\b(negative[\s_-]*control|countermodel|counter[\s_-]*example|reductio\s+ad\s+absurdum|adversarial\s+test|failure\s+mode|what\s+needs\s+proof|where\s+we\s+overreached|where\s+we\s+got\s+carried\s+away|what\'?s\s+load[\s_-]*bearing)\b",
    re.IGNORECASE,
)
REPRODUCIBLE_RECEIPT_RE = re.compile(r"\b(SHA-?256|MD5|git\s+commit|receipt|reproducible\s+command|docker|lake\s+exe)\b", re.IGNORECASE)
EXACT_PROVENANCE_RE = re.compile(r"\b(source_path|provenance|mtime|corpus_sha256|packet_id|lossless_address)\b", re.IGNORECASE)

# Navigational references (tracked, zero rigor points)
REFERENCE_RE = re.compile(r"(?:\[[^\]]+\]\((https?://[^\)]+|[^\)]+\.[a-z]{2,4})\)|\[\[[^\]]+\]\]|\b(?:doi|arXiv):[0-9a-zA-Z./_-]+)", re.IGNORECASE)


def _diminishing_score(counts: int, weight_first: float, weight_subsequent: float, max_cap: float) -> float:
    if counts <= 0:
        return 0.0
    score = weight_first + (counts - 1) * weight_subsequent
    return round(min(score, max_cap), 2)


def evaluate_data_channel(text: str, code_blocks: list[tuple[str, str]]) -> tuple[float, list[str]]:
    """Channel 1: Structured Data & Observations (max 25)."""
    score = 0.0
    receipts = []

    # 1. Tables (Markdown & HTML)
    dividers = len(MD_TABLE_DIVIDER_RE.findall(text))
    html_tables = len(HTML_TABLE_RE.findall(text))
    total_tables = dividers + html_tables
    if total_tables > 0:
        rows = MD_TABLE_ROW_RE.findall(text)
        numeric_rows = [r for r in rows if re.search(r"\d", r)]
        if numeric_rows:
            table_pts = _diminishing_score(total_tables, 8.0, 3.0, 15.0)
            score += table_pts
            receipts.append(f"{total_tables} quantitative data table(s) (+{table_pts} pts)")
        else:
            score += 3.0
            receipts.append(f"{total_tables} structural table(s) without numeric data (+3.0 pts)")

    # 2. JSON structured data objects vs raw configs
    json_data_detected = 0
    json_meta_detected = 0
    for lang, block in code_blocks:
        if lang.lower() in ("json", "jsonl", "csv", "tsv"):
            has_numbers_or_arrays = bool(re.search(r"\d+\.\d+|\[\s*\{.*\}\s*\]", block, re.DOTALL))
            is_mere_config = bool(re.search(r"(version|config|author|description|package|settings)", block, re.IGNORECASE))
            if has_numbers_or_arrays and not (is_mere_config and len(block) < 300):
                json_data_detected += 1
            else:
                json_meta_detected += 1

    if json_data_detected > 0:
        data_pts = _diminishing_score(json_data_detected, 7.0, 3.0, 10.0)
        score += data_pts
        receipts.append(f"{json_data_detected} empirical dataset/observation block(s) (+{data_pts} pts)")
    elif json_meta_detected > 0:
        score += 2.0
        receipts.append(f"{json_meta_detected} structured metadata/config block(s) (+2.0 pts)")

    # 3. Numeric measurements and statistical density
    measures = NUMERIC_MEASURE_RE.findall(text)
    if len(measures) >= 2:
        meas_pts = _diminishing_score(len(measures) // 2, 4.0, 1.5, 7.0)
        score += meas_pts
        receipts.append(f"{len(measures)} quantitative measurements/statistics (+{meas_pts} pts)")

    return min(25.0, round(score, 1)), receipts


def evaluate_math_channel(text: str) -> tuple[float, list[str]]:
    """Channel 2: Mathematical Derivations (max 25)."""
    score = 0.0
    receipts = []

    # 1. Display equations (LaTeX / $$)
    display_eqs = len(DISPLAY_MATH_RE.findall(text))
    if display_eqs > 0:
        disp_pts = _diminishing_score(display_eqs, 7.0, 2.5, 14.0)
        score += disp_pts
        receipts.append(f"{display_eqs} display equation(s) (+{disp_pts} pts)")

    # 2. Operational variables & Greek symbols
    operators = set(m.lower() for m in MATH_OPERATORS_RE.findall(text))
    if operators:
        op_pts = _diminishing_score(len(operators), 3.0, 1.0, 5.0)
        score += op_pts
        receipts.append(f"{len(operators)} operational math variable(s)/operator(s) (+{op_pts} pts)")

    # 3. Step-by-step derivation sequence
    steps = len(DERIVATION_STEP_RE.findall(text))
    if steps >= 2:
        step_pts = _diminishing_score(steps // 2, 3.0, 1.5, 6.0)
        score += step_pts
        receipts.append(f"{steps} derivation step indicator(s) (+{step_pts} pts)")

    # 4. Inline math expressions
    inlines = len(INLINE_MATH_RE.findall(text))
    if inlines >= 3 and display_eqs == 0:
        score += 3.0
        receipts.append(f"{inlines} inline math expression(s) (+3.0 pts)")

    return min(25.0, round(score, 1)), receipts


def evaluate_formal_channel(text: str, code_blocks: list[tuple[str, str]]) -> tuple[float, list[str], list[str]]:
    """Channel 3: Formal Logic, Lean & Proof Infrastructure (max 25)."""
    score = 0.0
    receipts = []
    gaps = []

    # 1. Lean theorems & definitions
    lean_theorems = LEAN_THEOREMS_RE.findall(text)
    if lean_theorems:
        thm_pts = _diminishing_score(len(lean_theorems), 6.0, 2.0, 10.0)
        score += thm_pts
        receipts.append(f"{len(lean_theorems)} Lean theorem/definition(s) (+{thm_pts} pts)")

    # 2. Proof receipts vs Proof gaps (sorry / admit)
    proof_receipts = len(LEAN_BUILD_RECEIPT_RE.findall(text))
    proof_gaps = LEAN_GAP_RE.findall(text)

    if proof_gaps:
        gaps.append(f"{len(proof_gaps)} incomplete proof placeholder(s) detected ({', '.join(set(proof_gaps))})")

    if proof_receipts > 0:
        if not proof_gaps:
            rec_pts = _diminishing_score(proof_receipts, 5.0, 1.5, 8.0)
            score += rec_pts
            receipts.append(f"{proof_receipts} formal verification receipt(s) (+{rec_pts} pts)")
        else:
            score += 2.0
            receipts.append(f"{proof_receipts} partial proof receipt(s) with open gaps (+2.0 pts)")

    # 3. Formal logic notation
    logic_hits = len(FORMAL_LOGIC_RE.findall(text))
    if logic_hits >= 2:
        log_pts = _diminishing_score(logic_hits // 2, 3.0, 1.0, 5.0)
        score += log_pts
        receipts.append(f"{logic_hits} formal logic operator(s) (+{log_pts} pts)")

    # 4. Verifiable executable code blocks
    verified_code = [c for lang, c in code_blocks if lang.lower() in ("python", "lean", "lean4", "sql", "ahk", "rust", "cpp")]
    if verified_code:
        code_pts = _diminishing_score(len(verified_code), 2.5, 1.0, 4.0)
        score += code_pts
        receipts.append(f"{len(verified_code)} verifiable algorithm/code block(s) (+{code_pts} pts)")

    return min(25.0, round(score, 1)), receipts, gaps


def evaluate_falsification_channel(text: str) -> tuple[float, list[str]]:
    """Channel 4: Falsification, Testing & Receipts (max 25). Zero points for citations."""
    score = 0.0
    receipts = []

    # 1. Explicit Kill Conditions / Falsifiers
    kill_conditions = KILL_CONDITION_RE.findall(text)
    if kill_conditions:
        kill_pts = _diminishing_score(len(kill_conditions), 7.0, 3.0, 10.0)
        score += kill_pts
        receipts.append(f"{len(kill_conditions)} explicit kill condition/falsifier(s) (+{kill_pts} pts)")

    # 2. Concrete testable predictions
    predictions = PREDICTION_RE.findall(text)
    if predictions:
        pred_pts = _diminishing_score(len(predictions), 4.0, 2.0, 6.0)
        score += pred_pts
        receipts.append(f"{len(predictions)} concrete testable prediction(s) (+{pred_pts} pts)")

    # 3. Negative controls / countermodels / adversarial tests
    controls = len(NEGATIVE_CONTROL_RE.findall(text))
    if controls > 0:
        ctrl_pts = _diminishing_score(controls, 2.5, 1.0, 4.0)
        score += ctrl_pts
        receipts.append(f"{controls} negative control/countermodel reference(s) (+{ctrl_pts} pts)")

    # 4. Reproducible run / calculation / dataset receipts
    repro_receipts = len(REPRODUCIBLE_RECEIPT_RE.findall(text))
    if repro_receipts > 0:
        repro_pts = _diminishing_score(repro_receipts, 2.0, 1.0, 3.0)
        score += repro_pts
        receipts.append(f"{repro_receipts} reproducible build/hash receipt(s) (+{repro_pts} pts)")

    # 5. Exact provenance (source path, lossless address, timestamp)
    provenance_hits = len(EXACT_PROVENANCE_RE.findall(text))
    if provenance_hits > 0:
        score += 2.0
        receipts.append("exact provenance/address metadata present (+2.0 pts)")

    return min(25.0, round(score, 1)), receipts


def score_structural_evidence(text: str) -> dict[str, Any]:
    """Master scoring function: returns Structural Evidence Profile v2."""
    if not text or not isinstance(text, str):
        return {
            "version": VERSION,
            "total_score": 0.0,
            "channels": {"data": 0.0, "math": 0.0, "formal": 0.0, "falsification": 0.0},
            "detected_artifacts": [],
            "proof_gaps": [],
            "navigational_references": 0,
            "evidence": 0.0,
            "evidence_density": 0.0,
        }

    # Extract code blocks
    code_blocks = CODE_BLOCK_RE.findall(text)

    # Count navigational references (pure metadata, 0 points)
    references_detected = len(REFERENCE_RE.findall(text))

    # Evaluate all 4 channels
    data_score, data_receipts = evaluate_data_channel(text, code_blocks)
    math_score, math_receipts = evaluate_math_channel(text)
    formal_score, formal_receipts, proof_gaps = evaluate_formal_channel(text, code_blocks)
    falsif_score, falsif_receipts = evaluate_falsification_channel(text)

    total = round(data_score + math_score + formal_score + falsif_score, 1)
    total_capped = min(100.0, total)

    all_receipts = data_receipts + math_receipts + formal_receipts + falsif_receipts
    if references_detected > 0:
        all_receipts.append(f"{references_detected} navigational reference(s) detected (0 pts - authority does not transfer truth)")

    return {
        "version": VERSION,
        "total_score": total_capped,
        "channels": {
            "data": data_score,
            "math": math_score,
            "formal": formal_score,
            "falsification": falsif_score,
        },
        "detected_artifacts": all_receipts,
        "proof_gaps": proof_gaps,
        "navigational_references": references_detected,
        # Backward compatibility aliases
        "evidence": total_capped,
        "evidence_density": total_capped,
    }
