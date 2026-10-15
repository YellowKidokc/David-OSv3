# 04_ADAPT — old cards get their stamp

Runs after 03_CLASSIFY's reviewer tells you a folder of cards "isn't mim.v1".
Legacy glossary cards (the `type: "definition"` / `status:` / `name:` schema)
can't be read by the classifier until they carry the `mim.v1` contract from
TAG_TAXONOMY_v0.4 Part B.3. This tool stamps them — mechanically.

## The rule

> If a script can do it without judgment, do it before the classifier.
> If it needs judgment, it goes through the classifier and you.

So the adapter translates only what has one right answer:

| Legacy field | Becomes | Note |
|---|---|---|
| *(new)* | `sidecar: mim.v1` | the stamp |
| filename | `subject:` | reviewer contract: subject = filename |
| `source_file` | `source_file` + `source: "[[basename]]"` | carried / derived |
| `status` | `standing:` | **only** if on the closed list, else left blank |
| *(new)* | `folder_class: glossary` | |
| *(new)* | `adapted_from` / `adapted_at` | provenance |
| everything else | carried verbatim | nested lists (`related_terms:`) survive |
| body | untouched | everything below the closing `---` |

`domain`, `ct-`/`ep-`/subject tags, and any `standing` the adapter couldn't
map stay **blank** — the Sidecar Review GUI flags them, the engines and
DeepSeek suggest, David rules. The adapter never guesses.

## Run it

```
ADAPT.bat "C:\path\to\glossary folder"
```

or drag a folder onto `ADAPT.bat`, or run it bare and pick a folder.

- **Originals are never touched.** Output lands in `04_ADAPT/OUTBOX/<folder name>/`
  (second argument overrides).
- Cards already stamped `mim.v1` are skipped; files with no frontmatter are
  counted as failures with a reason; every file prints a line, and the run
  ends with stats.
- Then open the Sidecar Review GUI (`03_CLASSIFY/REVIEW.bat`) on the outbox
  folder and rule the blanks.

## What it feeds

The outbox folder is a clean `mim.v1` card set: the reviewer
(`gui/review.py`) reads every card, the prediction harness
(`harness/adapters/sidecars.py`) learns from your rulings, and the taxonomy
validator (`00_SHARED/taxonomy_validator.py`) can check the result.
