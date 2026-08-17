# Folder Label Example

This is the kind of label a folder should get. It is not a creative summary.
It is a deterministic rollup of facts from:

- child files,
- scanner symptoms,
- semantic classifications,
- extension counts,
- job/action ledger,
- operator rules.

The folder does not invent a domain. It borrows domains from the files inside
it and reports the strongest evidence.

## Example `.folder.fmeta`

```json
{
  "schema": "top-ai-fis.folder_marker.v1",
  "folder_id": "fld_01JZ7_demo_downloads",
  "current_path": "D:/Downloads/AI Exports",
  "current_name": "AI Exports",
  "previous_names": ["New Folder", "AI stuff"],
  "previous_paths": ["D:/Downloads/New Folder"],
  "parent_path": "D:/Downloads",
  "first_seen_at": "2026-06-22T14:10:00-05:00",
  "last_seen_at": "2026-07-03T16:44:00-05:00",
  "first_scanned_at": "2026-07-01T08:15:00-05:00",
  "last_scanned_at": "2026-07-03T16:44:00-05:00",
  "scan_count": 7,
  "history": {
    "rename_count": 2,
    "move_count": 1,
    "file_in_count": 143,
    "file_out_count": 18,
    "file_delete_proposal_count": 12,
    "file_soft_delete_count": 0,
    "archive_proposal_count": 31,
    "restore_count": 0,
    "last_change_at": "2026-07-03T15:58:00-05:00"
  },
  "inventory": {
    "file_count": 125,
    "folder_count": 4,
    "total_bytes": 884211203,
    "extension_counts": {
      ".md": 42,
      ".txt": 31,
      ".json": 18,
      ".html": 14,
      ".png": 9,
      ".pdf": 6,
      ".zip": 3,
      ".zzz": 2
    },
    "kind_counts": {
      "text": 73,
      "data": 18,
      "web": 14,
      "image": 9,
      "document": 6,
      "archive": 3,
      "unknown": 2
    }
  },
  "classification_rollup": {
    "domain_counts": {
      "coding": 34,
      "research": 29,
      "ai_hub": 22,
      "theology": 14,
      "media": 9,
      "finance": 3,
      "unknown": 14
    },
    "top_domains": [
      {"domain": "coding", "count": 34, "percent": 27.2},
      {"domain": "research", "count": 29, "percent": 23.2},
      {"domain": "ai_hub", "count": 22, "percent": 17.6},
      {"domain": "theology", "count": 14, "percent": 11.2},
      {"domain": "media", "count": 9, "percent": 7.2}
    ],
    "classification_counts": {
      "indexed": 102,
      "needs_review": 17,
      "quarantine": 2,
      "duplicate_candidate": 4
    },
    "semantic_variable_totals": {
      "G": 12.4,
      "M": 18.2,
      "E": 79.1,
      "S": 64.7,
      "T": 21.3,
      "K": 33.5,
      "R": 11.0,
      "Q": 8.4,
      "F": 16.8,
      "C": 19.6
    },
    "dominant_semantic_variables": [
      {"variable": "E", "label": "epistemic/research", "score": 79.1},
      {"variable": "S", "label": "structural/code", "score": 64.7},
      {"variable": "K", "label": "knowledge/community", "score": 33.5}
    ],
    "confidence_summary": {
      "high": 77,
      "medium": 31,
      "low": 17
    }
  },
  "symptoms_and_anomalies": {
    "symptom_counts": {
      "S01": 1,
      "S02": 9,
      "S04": 1,
      "C01": 4,
      "C06": 2,
      "R02": 13
    },
    "anomaly_count": 7,
    "anomalies": [
      {
        "type": "unknown_extension",
        "symptom_id": "C06",
        "count": 2,
        "example_paths": ["D:/Downloads/AI Exports/cache_dump.zzz"]
      },
      {
        "type": "duplicate_cluster",
        "symptom_id": "C01",
        "count": 4,
        "example_paths": ["D:/Downloads/AI Exports/claude_export_copy.md"]
      },
      {
        "type": "version_sprawl",
        "symptom_id": "S02",
        "count": 9,
        "example_paths": ["D:/Downloads/AI Exports/final_FINAL_2.txt"]
      }
    ],
    "critical_findings": [],
    "program_root_markers": []
  },
  "policy": {
    "role": "inbox",
    "safety_zone": "review_required",
    "labels": ["inbox", "mixed_content", "has_anomalies"],
    "importance": "medium",
    "protected_reason": null,
    "action_policy": {
      "scan": "allowed",
      "hash": "allowed",
      "classify": "allowed",
      "write_sidecar": "review_required",
      "rename": "suggest_first",
      "move": "review_required",
      "archive": "review_required",
      "delete": "blocked",
      "bulk_restructure": "review_required"
    },
    "review_policy": {
      "bulk_rename_threshold": 20,
      "bulk_move_threshold": 20,
      "delete_requires_review": true,
      "unknown_extension_blocks_delete": true
    }
  },
  "provenance": {
    "source": "folder_scanner",
    "scanner_version": "folder_scanner.v1",
    "ruleset_versions": [
      "scanner_pipeline.v1",
      "label_enforcement.v1",
      "folder_label_schema.v1"
    ],
    "derived_from_file_count": 125,
    "derived_from_event_count": 174,
    "deterministic": true
  }
}
```

## Program Folder Example

If the folder is a program root, the rollup is still deterministic, but the
policy changes:

```json
{
  "schema": "top-ai-fis.folder_marker.v1",
  "current_path": "D:/GitHub/TOP AI FIS",
  "role": "program_root",
  "safety_zone": "protected",
  "labels": ["program_root", "protected", "do_not_delete", "do_not_move"],
  "inventory": {
    "file_count": 842,
    "extension_counts": {
      ".py": 139,
      ".md": 84,
      ".json": 41,
      ".jsx": 14,
      ".ahk": 31
    }
  },
  "evidence": {
    "program_root_markers": [".git", "pyproject.toml", "package.json"],
    "symptoms": ["I01"]
  },
  "action_policy": {
    "scan": "allowed",
    "hash": "allowed",
    "classify": "allowed",
    "rename": "blocked",
    "move": "blocked",
    "archive": "blocked",
    "delete": "blocked",
    "bulk_restructure": "blocked"
  }
}
```

That is the key distinction:

```text
folder label = biography + inventory + rollup + symptoms + policy
file label = identity + classification + anomalies + file-specific policy
```
