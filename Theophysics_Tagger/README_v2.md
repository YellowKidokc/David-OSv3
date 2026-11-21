# Theophysics Convergence Tagger v2

Tags documents against your registry with four layers, measures itself against a hand-checked
gold set, and tunes its own settings to that set. Read-only unless you pass a write flag.
(v1 is still at `tools/tagger.py`; its notes are in `README_v1.md`.)

## Daily use

```powershell
# tag a folder (words layer only)
python C:\Theophysics_Tagger\tools\tagger2.py scan --source "C:\path\to\papers"

# same, plus the meaning layer (needs Ollama running: `ollama serve`)
python C:\Theophysics_Tagger\tools\tagger2.py scan --source "C:\path\to\papers" --semantic
```

Re-running is cheap: unchanged files are skipped (identity = content hash, so moving or
renaming a file does not re-tag it). Editing any file in `01_REGISTRY` re-tags automatically.

## What each layer does

1. **Words.** Stemmed matching (grace/graces, sanctified/sanctification), CamelCase tags
   auto-split (HolySpirit -> "Holy Spirit"), longest phrase wins ("Holy Spirit" does not also
   fire Holiness), title x3 / heading x2 weighting, tf-idf, and a minimum-hit gate so one
   passing mention does not tag a document.
2. **Disambiguation** (all plain files in `01_REGISTRY`, edit freely):
   - `ambiguous_terms.txt` - common-English tags (rest, will, word, calling ...) count only
     when capitalized mid-sentence: "the Word", "Free Will", "Sabbath Rest".
   - `exclusions.csv` - `tag,phrase`: drop the tag in any paragraph containing the phrase
     (Grace / "grace hopper").
   - `category_weights.csv` - down-weight whole categories (Paper-derived topic = 0.5).
   - Tags whose stems collide (Pentecost / Pentecostal) fall back to exact matching.
3. **Meaning** (`--semantic`, Ollama `nomic-embed-text`). Each tag's definition is compared
   with every paragraph. A tag counts only if it stands far above that document's own
   baseline (z-score), so "a gift you did not earn" can find a tag without its keyword.
   It is only as good as the registry `description` column - 672 of 1,159 tags are empty.
4. **Scripture.** References like `Eph 2:8-9`, `1 Cor 13:4`, `Psalm 23` are extracted to
   their own CSV. "Mark 2 points" and "Job 3" are not taken as verses.

## Outputs (02_INDEX, one set per run, all in `tagger.db` too)

- `*_document_tags.csv` - primary tag, primary category (rolled up from all tags), scored tags,
  meaning-only tags, Master Equation variables, duplicate copies of the same content.
- `*_folder_suggestions.csv`, `*_scripture_refs.csv`
- `*_registry_audit.csv` - every tag with how often it fired. Tags at 0 are dead or mis-worded.
- `--export-paragraphs` adds paragraph-level hits with text snippets.

## Making it measurably better (the gold set)

1. `python tools\tagger2.py gold-template -n 50` writes `06_REVIEW\gold_template.csv`.
2. Fix the `correct_tags` column by hand (add what's missing, delete what's wrong).
3. Save it as `06_REVIEW\gold.csv`.
4. `python tools\tagger2.py eval` -> precision / recall / F1, plus the tags most often
   wrong and most often missed (feed those into the files in step 2 above).
5. `python tools\tagger2.py tune` -> grid-searches the settings, saves
   `06_REVIEW\tuned_params.json`, which every later scan uses automatically.

## Write flags (off by default)

- `--copy-by-primary-tag` copies (never moves) files into `03_TAGGED/<category>/<tag>/`.
- `--write-frontmatter` writes an `auto_tags:` list into `.md` frontmatter. It never touches
  your own `tags:` field, and it does not change the content hash.
