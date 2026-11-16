# Draft PR review: assertions, dependency and portability

The implementation revisions are David-OS `5d6d2f7d4b906e9e6eebf06f6fed9d9ed46cab4a`
and Prediction_GUI `b51686ee378d8b103a0faf373c9cf53dee39be43`.
Both PRs remain draft. Nothing was merged and no startup service was installed.

## 1. Every changed assertion and why

[ASSERTION_CHANGES.md](ASSERTION_CHANGES.md) lists the exact old/new code, file,
function and reason for every assertion difference against the two PR bases.
[ASSERTION_CHANGES.json](ASSERTION_CHANGES.json) is the machine-readable inventory.
It includes Python assertions, unittest assert calls and pytest exception expectations:
44 change groups, 5 removed/replaced statements and 124 added/replacement statements.
Pure moves into the historical archive are excluded.

| Existing assertion | Change and reason |
| --- | --- |
| FIS import allowlist | Permit only the named canonical identity, review and naming modules, alongside standard library/FIS modules. Preserve a closed boundary after consolidation. |
| Exact wheel package list | Include the canonical shared, FIS, prediction and tagger packages, and the already-present folder_hub/rule_brick packages. The former expectation was stale. |
| Notification status expectation | Change `[approved, pending]` to `[pending, pending]`: confidence must never authorize a GUI suggestion. The test is also renamed. |
| Two duplicate popup stdout assertions | The corresponding implementations were archived intact; active files now forward to Tagger v3 and own no subprocess. These are runtime assertions, not suppressed test failures. |

All other entries add regression coverage: identity issuance/aliases and path reuse,
immutable review receipts, restart/replay/rollback, App 160 compatibility, legacy
forwarding, config relocation, environment credentials and system protection on any drive.
Existing assertions were not loosened in this portability follow-up.

## 2. Prediction_GUI declares and installs David-OS

`requirements.txt` includes `-r requirements-david-os.txt`. The latter declares:

```text
david-os @ git+https://github.com/YellowKidokc/David-OSv3.git@5d6d2f7d4b906e9e6eebf06f6fed9d9ed46cab4a
```

`setup_env.py --core` installs this required dependency; normal setup also installs
optional inference/NLP packages. There is no sibling-checkout or backend PYTHONPATH
requirement. Setup forces replacement of the backend, because two commits can have
the same Python package version and ordinary pip installation can retain the older one.

A separate GUI clone named `gui with spaces` was set up and launched from an unrelated
working directory. Both `prediction` and `shared` imported from that clone's local
venv site-packages. Installed `direct_url.json` was checked against the exact commit
above, including after upgrading an environment that held an older same-version pin.
All 9 GUI tests, the existing nine-engine smoke and actual Tk window creation passed.
A separate backend clone with spaces also completed setup and ran the FIS CLI.

## 3. Linux workflow after the rename/identity fix

The original post-fix Linux run [43733260171](https://github.com/YellowKidokc/David-OSv3/actions/runs/43733260171)
passed at `be71fed`: 329 repository tests, 14 identity/classifier contracts with
4 unavailable-prerequisite skips, companion tests/smoke, and both wheel builds.

The completed portability code passes locally: **339 repository tests**, including
native GUI tests and real paired HTTP acceptance; contracts remain **14 passed,
4 skipped**. Ten additional parametrized portability cases account for the increase.
The companion's final CI [43779524351](https://github.com/YellowKidokc/Prediction_GUI/actions/runs/43779524351)
also passed.

The final-code Linux run [43779507420](https://github.com/YellowKidokc/David-OSv3/actions/runs/43779507420) passed at `5d6d2f7`, including repository/paired acceptance, identity/classifier contracts, companion compatibility and both wheel builds. The Windows FIS safety/build run [43779507729](https://github.com/YellowKidokc/David-OSv3/actions/runs/43779507729) also passed.

## 4. Large tagger CSVs

The two largest CSVs were 83,774,051 and 95,316,149 bytes. They and the other two
large generated indexes are now deterministic gzip archives under
`_archive/tagger-index/`: 269,785,384 original bytes become 58,593,695 bytes.
Each archive was decompressed and compared byte-for-byte before removing the
working-tree CSV. The manifest records original paths/sizes/hashes and archive
sizes/hashes; the archive README gives restoration instructions.

The live tagger and wheel do not require these historical outputs. Shared Git
history was not rewritten, so older commits still contain the original blobs.

## 5. Portability changes

- Both repositories have `config.example.yaml`, `setup_env.py`, `bootstrap.py` and
  `run.py`, with clone → setup → run instructions in their READMEs.
- Venvs default to local OS cache/AppData storage outside the clone. Each clone gets
  a distinct path. `DAVID_OS_VENV` overrides it; setup rejects network filesystems
  on Linux and non-fixed drives on Windows. Paths containing spaces are supported.
- Launchers use the configured local environment. Corpus operations accept explicit
  folder arguments or configured paths instead of personal drive defaults.
- YAML paths resolve relative to the config file, with environment overrides.
  `PORTABLE_PATH_SETTINGS.json` lists 42 former machine-bound defaults across 27
  additional standalone tools and their YAML/environment settings.
- Fresh watch profiles and folder registries have no selected corpus roots. Search
  defaults to the clone. Original machine configuration is preserved in the archive.
- Provider API keys are resolved from environment variables only. The provider
  router rejects inline JSON keys and never persists them. YAML rejects credential
  fields. The one-off token-file provisioning helper was archived and its replacement
  consumes an environment variable without a local token JSON file or test message.
- System folders remain protected on every Windows drive and on Unix; ordinary
  similarly named folders are allowed. Generated FIS notes remain globally disabled.
- The runtime path scan found no drive-letter, numeric UNC-host, `/home/` or `/Users/`
  path literals in active Python defaults. Active BAT/PowerShell launchers have no
  hard-coded drive or personal network paths. Frozen source snapshots, reference
  imports, audit evidence and Windows-path test fixtures retain historical strings.

Validation used Linux. The Windows workflow status is reported with the CI evidence
above; no claim is made that native macOS setup was exercised.
