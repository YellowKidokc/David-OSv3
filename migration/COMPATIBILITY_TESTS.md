# Compatibility tests

An app becomes `canonical` only when all pass:

1. Its START.bat runs it with no other app running.
2. Output validates against its shared/contracts schema.
3. Parity: same input → same output as the legacy code (recorded in MIGRATION_RECEIPTS.jsonl).
4. The legacy path still works (via legacy-adapters stub) and prints the new location.
5. No import of another app (`apps/*` may import only `shared`).
