# Canon Guard

Canon Guard is a version-aware canonical-document gate. It scans Markdown,
text, TeX, and Lean files; extracts equations; detects authority conflicts and
configured claim drift; produces JSON suitable for CI; and applies only
explicitly approved, reversible repairs.

It does **not** decide canon from timestamps, filenames, or `#canon`. It does
**not** let an LLM silently rewrite equations. Substantive conflicts become
findings or a semantic-review packet for David to adjudicate.

## Set up

Requires Python 3.11+ and no third-party packages.

1. Put ratified canonical documents at the paths in `canon-manifest.toml`.
2. Give every canonical document an explicit semantic version.
3. Add its SHA-256 after the exact bytes are frozen:

   ```bash
   python -c "import hashlib,pathlib; p=pathlib.Path('canon/no-drift-master-equation.md'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
   ```

4. Encode supersession only after David rules on it. Never infer it from date.

## Use

```bash
python canon_guard.py /path/to/project -m /path/to/canon-manifest.toml
python canon_guard.py . -m canon-manifest.toml --format json -o canon-report.json
python canon_guard.py . -m canon-manifest.toml --review-packet semantic-review.json
python canon_guard.py . -m canon-manifest.toml --fix --show-diff
```

Exit codes: `0` clean/warnings only, `2` error or critical finding, `3`
configuration/runtime failure.

## Repair boundary

`--fix` only applies a rule when all three are true:

- the manifest declares an exact replacement;
- `safe_fix = true`;
- the match is deterministic.

Each changed file is copied under `.canon-guard/backups/<timestamp>/` before an
atomic replacement. Equations and law assignments should normally remain
`safe_fix = false`.

## What “deep understanding” means here

The deterministic layer understands declared authority, versions, equation
fingerprints, scoped claims, and known invariants. Cross-domain meaning still
requires adjudication. `--review-packet` exports the bounded evidence needed by
a human or an optional model, but its answer is advisory until accepted into
the manifest. This separation is the guard against semantic hallucination.

## Current source conflict that must be ruled

The supplied April README declares only two no-drift files canonical and
untouchable. Later July files also carry canonical status, and the July
derivation map mentions a “v3 Master Equation ruling.” The starter manifest
therefore registers the two April documents plus the binding Consilience Rule,
but does not pretend that the authority relationship has already been decided.

## Stop-and-ratify equation workflow

`equation_workflow.py` implements a strict learning loop:

```bash
python equation_workflow.py scan /corpus --catalog equation-catalog.json
```

The scanner stops on the first uncataloged equation and creates one immutable
review case. Independent AI reviewers append classifications and translations:

```bash
python equation_workflow.py review CASE.json \
  --reviewer agent-a --model MODEL --decision drift --confidence .94 \
  --math-translation "..." --plain-translation "..." \
  --canonical-id master-equation --proposed-replacement "..."
```

After the required reviews, David ratifies the decision:

```bash
python equation_workflow.py ratify CASE.json \
  --catalog equation-catalog.json --ratified-by David --human-ratified
```

The catalog then remembers that exact normalized equation and its mathematical,
plain-language, and theological translations. A ratified `drift` decision
generates its own `fixes/fix_eq_*.py`. That fix script verifies the original
file hash and exact match, then writes only:

- a corrected copy;
- a unified patch for inspection.

It never modifies the source. Choosing or applying a patch remains a separate
human-controlled operation.
