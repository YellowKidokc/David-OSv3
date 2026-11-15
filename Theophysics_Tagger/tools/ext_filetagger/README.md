# ext_filetagger: what filetagger had that Tagger v3 didn't

Folded in on 2026-11-14 at David's request ("fold filetagger into Tagger v3").

Tagger v3 (`../tagger3.py`) already replaced filetagger's core jobs: file catalog, duplicates, `.fmeta` sidecars, `.folder.fmeta` markers and watch mode. Those parts of filetagger are retired.

These are the pieces v3 did **not** have. They're copied here unchanged so the tagger has one home. They aren't wired into `tagger3.py` or the GUI yet; that's the next build step.

| File | What it does | Wire into v3 as |
|---|---|---|
| `chi_pipeline.py`, `chi_profiles.py`, `filetagger_chi.py`, `filetagger_chi_v2.py`, `show_chi.py` | χ (chi) coherence scoring per file, with the `.chi` sidecars | a `--chi` option on scan |
| `wordnet_expander.py`, `wordnet_cluster.py`, `wordnet_deep.py` | expands registry terms through WordNet synonyms and clusters | a `grow_tags.py` input |
| `claim_jurisdiction.py`, `show_site_claims.py` | decides which domain or jurisdiction owns a claim | the classify step |
| `extract_math.py`, `export_math_csv.py`, `read_math_templates.py` | pulls equations out of papers, exports them to CSV and Excel | a `--math` option (feeds `05_MATH_AUDIT`) |
| `gen_audit.py` | builds the HTML corpus audit (`corpus_audit.html`) | report output |
| `wrap_article.py` | wraps an article in the site template | probably belongs to the site pipeline, not the tagger; David to decide |
| `salvaged/` | old memory modules (episodic, semantic, working) plus `sentinel_mcp_server.py` and `file_watcher.py` | review only; likely retire (the watcher and daemon pattern breaks the no-resident-programs rule) |

Data that came with filetagger is in `../../data_filetagger/`: the consciousness math JSON and scan files, the equations CSV and xlsx, `MTL_CONSCIOUSNESS_COMBINED.xlsx`, `corpus_audit.html`, `expanded_profiles.json` and the sample sidecars.

The original copies at `tools/filetagger` and `tools/file-intelligence-sources/snapshots/filetagger` can be retired once this fold is confirmed.
