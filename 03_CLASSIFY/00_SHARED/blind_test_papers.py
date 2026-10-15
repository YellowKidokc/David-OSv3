"""Blind test: can DeepSeek predict each card's `standing` with the value hidden?
Runs twice — summary only, then with the real source paper — and saves the disagreements.

    python blind_test_papers.py ["<sidecars folder>"]

Writes data/blind_test_with_papers.json. Reads cards and papers only; never edits them.
Summary-only answers come from the cache when the card is unchanged (free).
Baseline 2026-10-13, summary only: 8/51 matched the card, 32 declined to guess.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deepseek_triage as ds   # noqa: E402
import source_papers as sp     # noqa: E402

DEFAULT = "//192.168.2.50/h_hp/Desktop/Folders/AXIOM_CLASSIFICATION_CANON_2026-07-25 (1)/sidecars"
ALLOWED = ["canon", "declaration", "freeze-candidate", "proposed", "draft", "reference", "superseded", "inert"]


def main(folder: Path) -> None:
    if not folder.is_dir():
        sys.exit(f"Can't open {folder} — is the NAS awake?")
    cards = []
    for p in sorted(folder.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="replace")
        st = re.search(r"^standing:\s*(\S+)", t, re.M)
        sf = re.search(r'^source_file:\s*"?([^"\n]+)"?', t, re.M)
        if st:
            cards.append((p.stem, t, st.group(1), sf.group(1).strip() if sf else ""))
    found = sum(1 for c in cards if sp.find(c[3]))
    print(f"cards {len(cards)} | source papers found {found}")

    def run(c, with_paper):
        name, text, truth, sf = c
        return name, truth, ds.triage(text, "standing", ALLOWED, [], [], blind=True,
                                      paper=sp.excerpt(sf) if with_paper else "")

    res = {}
    for mode in (False, True):
        with cf.ThreadPoolExecutor(8) as pool:
            res[mode] = list(pool.map(lambda c: run(c, mode), cards))
    for mode, label in ((False, "SUMMARY ONLY"), (True, "WITH PAPER")):
        r = res[mode]
        print(f"{label:13} matches card {sum(1 for _, t, a in r if a.get('value') == t)}/{len(r)}"
              f" | no answer {sum(1 for *_, a in r if not a.get('value'))}"
              f" | errors {sum(1 for *_, a in r if a.get('_error'))}")
    out = [{"card": n, "card_says": t, "with_paper": a1.get("value"), "confidence": a1.get("confidence"),
            "reason": a1.get("reason"), "question": a1.get("question"), "summary_only": a0.get("value")}
           for (n, t, a0), (_, _, a1) in zip(res[False], res[True]) if a1.get("value") != t]
    dst = HERE / "data" / "blind_test_with_papers.json"
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(out)} card(s) where the paper-reading answer differs from the card -> {dst}")
    for o in out:
        print(f" - {o['card']}: card={o['card_says']}  paper→{o['with_paper']} ({o['confidence']})  {str(o['reason'])[:140]}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main(Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
