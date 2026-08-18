# CODEX BUILD PROMPT — FIS Symptom Detection Functions
# POF 2828 | 2026-08-17 | Written by Opus for Codex execution
# Location: D:\GitHub\David-OSv3\David-OS-tagger-publish\engine\symptoms\

---

## WHAT YOU'RE BUILDING

Implement every detection function from the Folder Symptom Registry.
36 symptoms across 6 categories. Each has a named function, detection
method, severity, and auto-fixable flag. Write the Python that detects them.

## SOURCE OF TRUTH

Three Excel files in this folder:

- `folder_symptom_registry.xlsx` — 36 symptoms (S01-R08), categories,
  detection methods, severity, auto-fixable flags, function signatures
- `FIS_Rule_Automation_Grammar.xlsx` — Full rule engine: Fields (60+),
  Operators (35), Actions (32), Guardrails, Compatibility, Workflows
- `FIS_SYSTEM.xlsx` — System config and integration spec

READ ALL THREE COMPLETELY BEFORE WRITING CODE.

## OUTPUT STRUCTURE

```
engine/symptoms/
├── __init__.py          — run_all_symptoms(folder_path) -> SymptomReport
├── models.py            — SymptomResult dataclass, SymptomReport, severity enum
├── structural.py        — S01-S08
├── content.py           — C01-C08
├── temporal.py          — T01-T04
├── infrastructure.py    — I01-I08
├── naming.py            — N01-N04
├── research.py          — R01-R08
└── tests/test_symptoms.py
```

## FUNCTION CONTRACT

```python
def detect_<name>(folder_path: Path, **kwargs) -> list[SymptomResult]:
```

```python
@dataclass
class SymptomResult:
    symptom_id: str       # "S01"
    severity: str         # low | medium | high | critical
    file_or_folder: str   # affected path
    description: str      # human-readable finding
    auto_fixable: bool
    recommended_action: str
    evidence: dict        # counts, names, hashes
```

## RULES

1. Match detection methods from the registry exactly.
2. I01/I03 (auto-fixable: NEVER) — detect only, NEVER modify.
3. Each function: one folder path. Caller handles recursion.
4. No pip deps beyond stdlib + existing engine modules.
5. Guardrails from the Grammar spreadsheet apply:
   - GR-004: NEVER auto-modify .env, credentials, config
   - GR-005: NEVER touch .git, node_modules, venv
   - GR-006: ALWAYS preview before destructive actions
6. run_all_symptoms() returns SymptomReport with:
   total, by_severity, by_category, findings[], clean_score (0-100)
7. Write real tests with tmp_path fixtures. No mocks.

## BUILD ORDER

1. models.py
2. structural.py (S01-S08)
3. naming.py (N01-N04)
4. content.py (C01-C08)
5. temporal.py (T01-T04)
6. infrastructure.py (I01-I08)
7. research.py (R01-R08)
8. __init__.py
9. tests/test_symptoms.py

Commit after each: `codex: symptoms/<file> — <what>`

## INTEGRATION

inventory_scan.py calls run_all_symptoms() per folder.
Results feed FIS.html health section + SQLite symptoms table +
action script generator.

*Read the Excel files. Build what they describe. Don't add, don't subtract.*
