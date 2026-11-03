# FIS naming schema
POF 2828 | Oct 25, 2026 | the dedicated schema for file names and classifications

Machine-readable form: `docs/schemas/fis-naming-vocabulary.schema.json`.
Why and how it is used: `docs/FIS_NAMING_OPERATING_PRINCIPLES.md`.

Status key: **[built]** exists today. **[proposed]** agreed, not yet implemented.

## 1. The name [built]
```
DOMAIN__TYPE__title_words__YYYYMMDD__STATUS.ext
```

| Part | Format | Source | If nothing matches |
|---|---|---|---|
| DOMAIN | 3 capitals | domain rules | `GEN` |
| TYPE | 3 capitals | type rules | `ART` |
| title_words | lowercase, `_` separated, at most 7 words | filename or first `# ` heading | none |
| YYYYMMDD | 8 digits | file modified time | none |
| STATUS | 2 capitals | status rules | `AC` |

A stem already matching `^[A-Z]{3}__[A-Z]{3}__.*__\d{8}__[A-Z]{2}$` is left alone. The whole name is capped at 150 characters.

## 2. Two tiers of vocabulary
The schema has a **core** and a **learned** tier. Core is authoritative.

### Core tier [built]
Shipped, versioned, and never edited by FIS itself.
- `fis/data/naming.json`: the general codes (domains CON COS FRM INF SOC FAM SCI PHY; types TMP TAN REF RES NOT INS DAT TST DRV CHP PAP AUD STY ART; statuses DR FN AR RV), fallbacks, series patterns, drop words, protected names.
- `fis/data/theophysics.json`: the Theophysics core, with domains MEQ AXM GRC ETH THE TPH. This is the opt-in `theophysics` rule pack. Its domains are tried before the general ones.

The Theophysics core is the intended home for the framework's own classifications. Extend it by hand: add keywords to an existing domain's `words`, or add a domain with a new unused code.

### Learned tier [proposed]
Where FIS records classifications it created because the core had none.
- File: `vocabulary.user.json` in the FIS state directory, in the same shape as core files, with a `provenance` block on each rule.
- Loaded after core. Core always wins a tie. A learned rule can never override or remove a core rule.
- Shipped core files stay untouched, so undoing the learned tier means reverting one file.

## 3. Creating a new classification [proposed]
FIS may create a new keyword, domain, or type when the core cannot classify a file.

1. **Trigger.** A file falls back (`GEN`, `ART`, or no keyword), and a term recurs. The counter (principles doc, section 5) tracks distinct files and folders. A term you type while correcting a name counts for more. An optional AI provider may also suggest terms; it feeds the same counter.
2. **Creation.** On crossing the threshold, FIS creates the rule in the learned tier with state `provisional`.
   - A new keyword attaches to the best existing domain or type.
   - A new domain gets a proposed three-capital-letter code derived from the term (biophysics suggests `BIO`). The code must not collide with any core or learned code or fallback. On a collision FIS tries other letter combinations from the term.
3. **Use.** A provisional rule is usable immediately in proposals. A name that used one is flagged **new class** in review, with the evidence (count and example files) one click away.
4. **Confirmation.** Because every rename already needs approval, approving a row that used a provisional code is the confirmation, and the rule becomes `confirmed`. Rejecting it records a block (state `rejected`), so it is not proposed again.
5. **Never automatic into canon.** Axiom or canon-bearing terms follow the same path but stay `provisional` until a person confirms them explicitly; nothing promotes into the Theophysics core file automatically.

### Constraints on any created rule
- Codes: domain and type are exactly three capitals `A-Z`, status exactly two.
- Each rule has a non-empty `words` list; words are at least two characters.
- Every learned rule carries `provenance`: `created_by` (`counter`, `ai`, or `user`), `state`, `created`, counts, up to five example paths, and a reason.
- No more than one rule per code. Fallback codes (`GEN`, `ART`, `AC`) are reserved.
- A learned rule may only be added through the validated writer, which checks the JSON Schema before saving. A file failing validation is ignored with a visible warning, and the core still works.

## 4. Matching order [built]
1. Filename, then title, then folder, then body (first 4000 characters).
2. In filename, title, and folder, the first rule in list order wins; list order is priority.
3. In the body, the rule with the most keyword hits wins, with at least three.
4. Core Theophysics domains come before the general core. Learned rules come after the core.
5. No hit: the fallback code, with the evidence line "No clue; configured fallback".

Confidence is 0.3 plus the domain weight (name 0.35, title 0.25, folder 0.20) plus the type weight. A row with no clue scores 0.30.

## 5. Gaps found on a real folder, and their status
Run on `theophysics-read\me` on 2026-10-25 (38 files):
- **Fixed in code** (`fis/naming_helpers.py`, `fis/rename.py`, tests in `tests/test_fis_naming.py`): leading zeros in series numbers are kept (`012_` stays `012_`); dotted IDs stay whole (`E2.1` becomes `e2_1`); CamelCase is split before matching; files named `LAW_NN_…` share the `LAW` domain; `.lean` files get `LEA` and scripts `SCR` when no other type matches.
- **Fixed by the learned tier** (now shipped as provisional rules): equation and law types `EQN`, `CRD` (law card), `EXP` (law expansion).
- **Registry-driven, draft:** a `LAW_NN` name resolves through the laws registry. When the person in the filename belongs to a different law than the number says (the Law 8/9 swap), the row gets a `hold` and confidence 0.3 instead of a guessed rename.
- **Built 2026-10-25 (`fis/vocabulary.py`, tests in `tests/test_fis_vocabulary.py`):** the learned loader and the suggestion counter. `service.scan` and the background service pass the learned tier and the laws registry to `propose()`. The shipped tier is `fis/data/vocabulary.learned.json` (51 provisional codes) and `fis/data/laws.registry.json` (draft). The user layer is `<state>/vocabulary.user.json`; the counter's ledger is `<state>/vocabulary.candidates.json`. Thresholds: a new domain or type needs 15 distinct files across at least 3 folders, with at most 5 promotions per scan. Review with `fis vocab`, then `--confirm CODE` or `--reject CODE`.
- **Still open:** body-keyword counting can still pick odd domains for ordinary files; dates in names are file modified times, not document dates; the Theophysics rule pack is off by default, so `MEQ`/`AXM`/`GRC` etc. only appear once it is enabled for a root; the counter only creates domains and types (a new keyword for an existing domain is still added by hand); and the GUI does not yet show provisional rules, only the `fis vocab` command does.

Result on that folder (default settings, pack off): files left on the generic `ART` type fell from 35 to 1; all ten `LAW_NN` files are in the `LAW` domain; the two with a number that disagrees with the registry are held.
