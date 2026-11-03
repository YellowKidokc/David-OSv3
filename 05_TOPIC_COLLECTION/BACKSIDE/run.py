"""Numbered doorway for topic discovery and explicitly selected copy-only collection."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from engine.topic_collection import plan_collection, review_html, collect_selection
from gui.drive_harvester import slugify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", type=Path)
    parser.add_argument("--collect", type=Path, help="Reviewed plan.json")
    parser.add_argument("--selection", type=Path, help="Selection JSON exported from REVIEW.html")
    parser.add_argument("--out", type=Path, help="New output directory")
    args = parser.parse_args()
    if args.collect:
        if not args.selection or not args.out:
            parser.error("--collect requires --selection and --out")
        result = collect_selection(json.loads(args.collect.read_text(encoding="utf-8-sig")),
                                   json.loads(args.selection.read_text(encoding="utf-8-sig")), args.out)
        print(result["status"], args.out.resolve(), flush=True)
        return 0 if result["status"] == "complete" else 1
    requests = [args.request] if args.request else sorted((ROOT / "INBOX").glob("*.json"))
    if args.out and len(requests) != 1:
        parser.error("--out requires one request")
    if not requests:
        print("No requests. Put a topic/roots JSON request in INBOX.")
    for path in requests:
        request = json.loads(path.read_text(encoding="utf-8-sig"))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = (args.out or ROOT / "OUTBOX" / (slugify(request.get("topic", "topic")) + "-" + stamp)).resolve()
        if out.exists():
            raise ValueError("Output must be new: " + str(out))
        print("SEARCH", request.get("topic"), request.get("roots"), flush=True)
        plan = plan_collection(request, exclude=[ROOT, out], progress=lambda message: print(message, flush=True))
        out.mkdir(parents=True)
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "REVIEW.html").write_text(review_html(plan), encoding="utf-8")
        print(f"DONE PLAN · {len(plan['files'])} matches · partial={plan['partial']} · {out / 'REVIEW.html'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
