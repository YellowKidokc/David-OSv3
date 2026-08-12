# FIS-Atlas

A clean, consolidated rebuild of the File Intelligence System, built back from
first principles. It turns a messy "everything goes here to die" folder into a
**file-and-folder atlas**: every object recorded, hierarchy preserved, similar
things clustered, every proposed action attached to *evidence* and *permission*.

## Design spine (what this actually is)

1. **The `.fisnote` is a node.** Every folder gets a note that carries identity,
   meaning (purpose / class / risk), permission (allowed/forbidden actions),
   memory (per-file event ledger), and a *declarative* capability manifest
   (watch/notify/schedule) — never embedded code.
2. **Four separate questions per object** — kept apart, never collapsed:
   *What is it? · What does it belong with? · How certain are we? · What are we
   authorized to do?* High certainty about identity does not grant permission.
3. **Resolve at the highest safe level** — whole folder → cluster → rule →
   individual object. 200 items become ~10–20 decisions.
4. **Rules are data, handlers are a shelf.** A dumb, stable core walks objects,
   evaluates a `WHEN … THEN …` rule grammar, and attaches only the op-coded
   handlers it needs at that moment.
5. **Programming/system/secrets folders are RED** — sealed on sight, checked
   before any other classification. Fail closed.

## Op-code vocabulary (the shared alphabet)

`lok` look/scan · `idn` identity/hash · `und` understand/classify ·
`sim` similarity · `dec` decide/propose · `act` execute · `gov` govern ·
`lrn` learn · `aut` automate

## Safety, non-negotiable

* **Preview only.** The scanner and classifier NEVER move, rename, or delete.
* Proposed sidecars/renames are written to `_atlas_out/`, not into your folders,
  unless you pass `--in-place` (off by default).
* Originals in the old scattered FIS trees are untouched; their heavy logic
  (NLP classify, near-dup) gets *ported* into the handler shelf over time.

## Run it

```
python run_atlas.py <folder>            # build the atlas, preview-only
python run_atlas.py <folder> --html     # + render the gold-on-black atlas page
python -m pytest                        # tests
```
