"""deep_identify_to_quickcall.py — Bridge: feed deep_identify results through 000_QUICK_CALL.

Takes a deep_identify report, selects files worth a DeepSeek pass, runs them
through quick_call, then merges the AI classification back into the report.

Selection criteria (any of):
  - doc_type == "paper" (always worth classifying)
  - identity_confidence < 0.5 (uncertain — let AI break the tie)
  - orphan_probability > 0.6 (might belong somewhere we missed)
  - family confidence < 0.7 (weak family — AI might see what we didn't)

Usage:
    python deep_identify_to_quickcall.py REPORT_DIR [--max-calls 30] [--dry-run]
    python deep_identify_to_quickcall.py REPORT_DIR --family FAM-001

Requires: DEEPSEEK_API_KEY in environment or Windows registry.
"""
from shared.runtime_config import path_setting as _portable_path
from pathlib import Path as _PortablePath
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the quick_call station to path
QUICK_CALL_DIR = Path(str(_portable_path('DAVID_OS_LEGACY_DEEP_IDENTIFY_TO_QUICKCALL_000_QUICK_CALL', 'legacy_deep_identify_to_quickcall_000_quick_call', _PortablePath(__file__).resolve().parents[2] / '_local/000_QUICK_CALL')))
sys.path.insert(0, str(QUICK_CALL_DIR))


def load_key():
    """Get DeepSeek API key from env or Windows registry."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")[0]
            os.environ["DEEPSEEK_API_KEY"] = key
            return key
    except Exception:
        return None


def select_files(report: dict, family_filter: str = "") -> list[dict]:
    """Pick files worth sending to DeepSeek."""
    selected = []
    for card in report.get("cards", []):
        # Skip non-documents
        if card.get("file_kind") not in ("document", "unknown"):
            continue
        # Skip tiny files
        if card.get("size_bytes", 0) < 100:
            continue

        reasons = []

        if family_filter:
            if card.get("family_id") == family_filter:
                reasons.append("family_filter_match")
            else:
                continue

        if card.get("doc_type") == "paper":
            reasons.append("is_paper")
        if card.get("identity_confidence", 1.0) < 0.5:
            reasons.append(f"low_confidence:{card.get('identity_confidence', 0):.2f}")
        if card.get("orphan_probability", 0) > 0.6:
            reasons.append(f"orphan:{card.get('orphan_probability', 0):.2f}")
        if card.get("family_id") and card.get("relationship_strength", 1.0) < 0.7:
            reasons.append(f"weak_family:{card.get('relationship_strength', 0):.2f}")

        if reasons:
            selected.append({
                "path": card["path"],
                "name": card["name"],
                "family_id": card.get("family_id", ""),
                "family_name": card.get("family_name", ""),
                "position": card.get("position_in_family", -1),
                "reasons": reasons,
                "pre_confidence": card.get("identity_confidence", 0),
            })

    # Sort: papers first, then low confidence, then orphans
    selected.sort(key=lambda x: (
        0 if "is_paper" in x["reasons"] else 1,
        x["pre_confidence"],
    ))
    return selected


def run_quickcall(file_info: dict, series_name: str = "", position: int = -1) -> dict:
    """Run one file through quick_call and return the result."""
    import quick_call

    kwargs = {"path": file_info["path"], "use_ai": True}
    if series_name:
        kwargs["series"] = series_name
    if position >= 0:
        kwargs["position"] = position

    try:
        side = quick_call.run(**kwargs)
        nabla = side.get("nabla", {})
        return {
            "path": file_info["path"],
            "status": nabla.get("status", "UNKNOWN"),
            "nabla_address": nabla.get("address"),
            "confidence": nabla.get("confidence", {}),
            "review_flags": nabla.get("review_flags", []),
            "minimal_decode": nabla.get("minimal_decode"),
            "truth_modes": nabla.get("truth_modes", []),
            "paper_uuid": side.get("identity", {}).get("paper_uuid"),
            "error": None,
        }
    except Exception as e:
        return {
            "path": file_info["path"],
            "status": "FAILED",
            "error": str(e),
        }


def merge_results(report: dict, ai_results: list[dict]) -> dict:
    """Merge AI classification results back into the deep_identify report."""
    result_by_path = {r["path"]: r for r in ai_results}

    for card in report.get("cards", []):
        ai = result_by_path.get(card["path"])
        if not ai:
            continue

        card["ai_status"] = ai["status"]
        card["ai_nabla_address"] = ai.get("nabla_address")
        card["ai_confidence"] = ai.get("confidence", {})
        card["ai_review_flags"] = ai.get("review_flags", [])
        card["ai_paper_uuid"] = ai.get("paper_uuid")

        # Adjust identity confidence based on AI result
        if ai["status"] == "VALID":
            # AI confirmed — boost confidence
            ai_conf_values = [float(v) for v in ai.get("confidence", {}).values() if v]
            if ai_conf_values:
                ai_avg = sum(ai_conf_values) / len(ai_conf_values)
                # Weighted merge: 40% structural, 60% AI
                old = card.get("identity_confidence", 0)
                card["identity_confidence"] = round(old * 0.4 + ai_avg * 0.6, 4)
                card["confidence_source"] = "structural+ai"
        elif ai["status"] == "INVALID":
            # AI disagreed — lower confidence, flag for review
            card["identity_confidence"] = round(card.get("identity_confidence", 0) * 0.5, 4)
            card["confidence_source"] = "structural+ai_invalid"

    # Recalculate family stats
    for fam in report.get("families", []):
        member_confs = [
            c.get("identity_confidence", 0)
            for c in report["cards"]
            if c.get("family_id") == fam["family_id"]
        ]
        if member_confs:
            fam["avg_member_confidence"] = round(sum(member_confs) / len(member_confs), 4)

    report["stats"]["ai_pass_completed"] = True
    report["stats"]["ai_files_processed"] = len(ai_results)
    report["stats"]["ai_valid"] = sum(1 for r in ai_results if r.get("status") == "VALID")
    report["stats"]["ai_invalid"] = sum(1 for r in ai_results if r.get("status") == "INVALID")
    report["stats"]["ai_failed"] = sum(1 for r in ai_results if r.get("status") == "FAILED")

    return report


def main():
    parser = argparse.ArgumentParser(description="Bridge deep_identify → quick_call")
    parser.add_argument("report_dir", type=Path, help="Directory with deep_identify.json")
    parser.add_argument("--max-calls", type=int, default=30, help="Max DeepSeek API calls")
    parser.add_argument("--family", type=str, default="", help="Only process one family (e.g. FAM-001)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without calling API")
    args = parser.parse_args()

    # Load report
    report_path = args.report_dir / "deep_identify.json"
    if not report_path.exists():
        print(f"ERROR: {report_path} not found. Run deep_identify.py scan first.")
        sys.exit(1)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(f"Loaded: {report['stats']['files_scanned']} files, {report['stats']['families_found']} families")

    # Select files
    selected = select_files(report, args.family)
    if not selected:
        print("No files selected for AI pass.")
        sys.exit(0)

    selected = selected[:args.max_calls]
    print(f"Selected {len(selected)} files for DeepSeek pass:")
    for f in selected:
        print(f"  {f['name']:50s}  reasons: {', '.join(f['reasons'])}")

    if args.dry_run:
        print("\n--dry-run: stopping here.")
        sys.exit(0)

    # Check API key
    if not load_key():
        print("ERROR: DEEPSEEK_API_KEY not found in environment or registry.")
        sys.exit(1)

    # Run through quick_call
    ai_results = []
    for i, file_info in enumerate(selected, 1):
        print(f"\n[{i}/{len(selected)}] {file_info['name']}...")
        result = run_quickcall(
            file_info,
            series_name=file_info.get("family_name", ""),
            position=file_info.get("position", -1),
        )
        ai_results.append(result)
        status = result.get("status", "?")
        addr = result.get("nabla_address", "")
        print(f"  -> {status}  {addr or result.get('error', '')}")

    # Merge back
    merged = merge_results(report, ai_results)

    # Write updated report
    out_path = args.report_dir / "deep_identify_with_ai.json"
    out_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Summary
    s = merged["stats"]
    print(f"\n{'='*60}")
    print(f"AI pass complete: {s['ai_files_processed']} files")
    print(f"  VALID:   {s['ai_valid']}")
    print(f"  INVALID: {s['ai_invalid']}")
    print(f"  FAILED:  {s['ai_failed']}")
    print(f"  Updated report: {out_path}")

    # Write notification payload for Prediction_GUI
    notifications = []
    for r in ai_results:
        card = next((c for c in merged["cards"] if c["path"] == r["path"]), None)
        if not card:
            continue
        if r.get("status") == "VALID" and card.get("family_id"):
            notifications.append({
                "type": "family_member_confirmed",
                "file": card["name"],
                "family": card.get("family_name", ""),
                "confidence": card.get("identity_confidence", 0),
                "nabla": r.get("nabla_address", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        elif card.get("orphan_probability", 0) > 0.5:
            notifications.append({
                "type": "orphan_detected",
                "file": card["name"],
                "confidence": card.get("identity_confidence", 0),
                "suggestion": "review for family assignment",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    if notifications:
        notif_path = args.report_dir / "notifications.json"
        notif_path.write_text(
            json.dumps(notifications, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  Notifications: {len(notifications)} -> {notif_path}")


if __name__ == "__main__":
    main()
