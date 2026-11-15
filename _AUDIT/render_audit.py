from pathlib import Path
import csv,json,html,re
from collections import defaultdict,Counter
ROOT=Path.cwd();A=ROOT/"_AUDIT"
OLD=r"D:\GitHub\pipeline-workflows\Codex-Powershell_GUI\David-OS"
V1=r"D:\GitHub\David-OS"
PG=r"D:\GitHub\Prediction_GUI"
def rows(name):
 with (A/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def save(name,keys,values):
 with (A/name).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.writer(f);w.writerow(keys);w.writerows(values)
def esc(x):return html.escape(str(x if x is not None else ""),quote=True)
def p(x):return "<p>"+esc(x)+"</p>"
def table(keys,values):
 return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in values)+'</tbody></table></div>'
def details(title,body):return '<details><summary>'+esc(title)+'</summary>'+body+'</details>'
def links(*names):return '<p>'+' · '.join('<a href="'+esc(x)+'">'+esc(x)+'</a>' for x in names)+'</p>'
def section(n,title,body):return f'<section id="s{n}"><h2>{n}. {esc(title)}</h2>{body}</section>'

STRUCTURAL=[
("Competing owners for FIS","Standalone fis/ owns a full local tag → classify → propose → approval/HTML loop. The legacy folder memory, Tk scanner and paper registry have different outputs. They cannot all be the first-pass owner.","fis/scan.py:62; fis/index.py:39; file-intelligence-system/fis_folder_memory.py:41; 06_FIS_HTML/registry_scan.py:387; gui/fis_scanner_gui.py:13"),
("SQLite and identity can split","Stage 1 registry.sqlite, engine filebrain.sqlite, standalone index.sqlite and Folder Hub relay.sqlite are separate. The direct JSON/CSV producers do not all first admit proposals to a per-drive registry.","engine/registry.py:282; engine/config.py:35; fis/index.py:39; folder_hub/service.py:34,70; apps/classify/src/run.py:60"),
("The classification stages do not compose","The MIM YAML reviewer, Rust lexicon, standalone FIS checks and deep-identify record different schemas. APOL can use local MiniLM and DeepSeek triage exists separately; these are not proof of a common local-first escalation policy.","03_CLASSIFY/02_CLASSIFICATION/gui/review.py; apps/classify/src/run.py; fis/tag.py; 10_FILE_ACTIONS/shared/{apol_shadow,deep_identify,scan_db}.py"),
("Public IDs need an authority gate","The registry can propose an S code from four hash characters, including letters. It also creates UUIDv4 version tokens internally. Nothing in that code proves a candidate is an issued numeric S####, or that internal tokens belong in filenames.","engine/registry.py:194–208,248; 06_FIS_HTML/registry_scan.py:136,415"),
("Prediction ownership is duplicated","03_CLASSIFY ships a harness; engine/preference and fis/preference contain naming learners; Prediction_GUI owns an independent runner, ledger and approvals. Rename-acceptance and next-event confidence are different targets.","03_CLASSIFY/02_CLASSIFICATION/{engines,harness}; engine/preference/ensemble.py; fis/preference; D:/GitHub/Prediction_GUI/harness"),
("A move can silently break the current HTML","Prediction_GUI serves FIS PICS HTML/simple.html by path. Its older guided actions still name localhost:61845; standalone FIS uses its own web boundary. Preserve the wrapper when changing either path.","FIS PICS HTML/simple.html:762; D:/GitHub/Prediction_GUI/API/server.py; fis/web.py"),
("Resident mechanisms are not one system","Installed CLI exposes watch/poll; separate hub and tagger watchers exist. October acceptance documents a sign-in installation. That receipt does not establish current appointment for every resident.","pyproject.toml:23–25; scripts/fis/INSTALL_BACKGROUND.ps1; docs/FIS_ALWAYS_ON_VERIFICATION.json; tools/filetagger/filetagger_daemon.py"),
("Generated state is mixed into source","The tracked GUI catalog and rename feed exceed 5 MB; a 6.98 GB match CSV sits under stage 10 and run trees contain recovery evidence. Moving them without mapping readers can break review and rollback.","_AUDIT/tracked_over_5mb.csv; 10_FILE_ACTIONS/logs; runs; .gitignore"),
]
# Role classification is a source observation, not a runtime claim.
FOLDERS={
"01_PROFILE":("FIS","live","Profile wizard; PROFILE.bat and rules capture folder context before classification."),
"02_INVENTORY":("FIS","live","RUN_INVENTORY.bat, engine.registry and engine.inventory_scan own the Stage 1 adapter boundary."),
"03_CLASSIFY":("Classify","live","MIM cards, validator, reviewer, renamer and local prediction adapters. Retain validation and route inference outward."),
"04_ADAPT":("Classify","live","ADAPT.bat mechanically stamps mim.v1; downstream depends on its output contract."),
"05_TOPIC_COLLECTION":("Content","live","Topic scan/selection/copy, GUI and batch; reuses gui/drive_harvester and engine/text_extractor."),
"06_FIS_HTML":("FIS","live","REGISTRY_SCAN.bat builds per-paper receipt view; different from the folder FIS sidecar."),
"10_FILE_ACTIONS":("Actions","live","File action launcher, deep classifiers, series grouping, scanners and generated logs."),
"fis":("FIS","live","Standalone CLI, scanner, index, web, gated rename and folder HTML; strongest first-pass candidate."),
"file-intelligence-system":("FIS","live","Compatibility classifiers and folder-memory SQLite; richer doc-type rules and legacy notes."),
"file-intelligence-hub":("Tooling","duplicate","Separate nested worktree with job/worker/watcher code; compare deltas before adopting."),
"folder_hub":("Tooling","live","Folder view/relay with read-only attached registries, not a mutation worker."),
"hub":("Tooling","live","Runtime API, workers, watchers, memory and notices. Root dos-* console scripts bind here."),
"engine":("Tooling","live","Shared registry, scan, classifier/search helpers, approval-bound writes and preference code. Preserve imports."),
"rule_brick":("Actions","live","Advisory questions, work evidence, and receipts; no mutation authorization."),
"shared":("Tooling","live","Contracts and cross-stage helpers. Keep stable imports."),
"config":("Tooling","live","Rules and runtime config. Separate host paths from tracked contracts."),
"apps":("GUI","live","App launchers and stage adapters. Root LAUNCH.bat discovers apps/*; includes classifier/fingerprint Rust."),
"gui":("GUI","live","Tk operational launchers; FIS scanner, intake and harvester. Holds tracked catalog DB."),
"FIS PICS HTML":("GUI","live","Simple FIS and many visual references. Prediction_GUI currently serves the exact Simple HTML path."),
"tools":("Tooling","live","Utilities, recovered organizer and tagger, HTML index duplicates, Rust kernel and Script Hub."),
"Theophysics_Tagger":("Classify","live","Tagger v3 GUI, evidence and SQLite catalog; START_TAGGER.bat. Optional watch and writes require review."),
"data":("Data","live","Versioned inputs and generated app output mixed, including tracked rename feed."),
"_data":("Data","live","Working registry and Stage 2 receipts. Default path shared by registry and mutation gate."),
".data":("Data","live","Ignored canonical workbook, comparison reports, inventories and shadow outputs; ownership differs by artifact."),
"runs":("Data","stale","Generated supervised merge/cleanup reports and recovery artifacts; retain by receipt."),
"runtime":("Data","live","Local generated runtime and tools; keep paths until consumers verified."),
"system":("Data","live","Touched-by-other-work JSONL ledgers and engine state. No migration in this audit."),
"archive":("Data","stale","Archive staging area; preserve provenance and receipt context."),
"migration":("Data","stale","Migration specifications and artifacts."),
"_FIS_ROOT_SIDECAR_ARCHIVE":("Data","stale","Cold sidecar archive and evidence; not normal crawl input."),
"LossLess":("Content","duplicate","Unpacked old Lossless script tree; two scripts match after line-ending normalization; namer differs."),
"_LOSSLESS_SUMMARY":("Content","live","More complete Lossless launcher, templates, sample papers and nested release."),
"LEAN 4":("Content","stale","Formal source/corpus tools plus excluded .lake dependencies. Build/runtime not tested."),
"canon_guard":("Content","live","Downstream canon review and audit, not first-pass FIS or identity issuance."),
"pipeline":("Content","live","Small Python downstream helpers; do not assign Rust content-engine ownership from this folder."),
"legacy-adapters":("Classify","live","Compatibility routines; keep until unified strategy has confirmed callers."),
"schemas":("Tooling","live","Versioned schemas. Keep with stable registry and approval contracts."),
"scripts":("Tooling","live","Windows and intake helpers, including explicit FIS background installer."),
"files":("Tooling","live","Inventory kits and local output directories; maintain related launchers together."),
"docs":("Tooling","live","Specs, handoffs and dated acceptance evidence, including historical source samples."),
"agents":("Tooling","stale","Agent packets and technical research examples; no current registration inferred."),
"deploy":("Tooling","live","Packaging/install artifacts, including Synology bundle; no runtime claim."),
"services":("Tooling","live","Runtime service definitions; keep activation explicit."),
"tests":("Tooling","live","Regression source/fixtures; no write-heavy test suite run."),
".github":("Tooling","live","GitHub integration root; preserve location."),
".git":("Control","live","Repository control metadata; contents skipped."),
".venv":("Generated","junk","Rebuildable Python environment; skip contents, retain active interpreter path."),
".wrangler":("Generated","junk","Local Cloudflare runtime, already ignored. Check active session before cleanup."),
".superpowers":("Data","stale","Local design/checkpoint evidence; retain until owner decides."),
"david_os.egg-info":("Generated","junk","Rebuildable package metadata; do not remove active installation."),
}
CLUSTERS={
"A · FIS":[("fis","Standalone approval-bound filesystem pipeline and SQLite","keep","Choose as first-pass FIS implementation."),("file-intelligence-system","Folder-memory FIS, doc-type classifier, legacy namer and DB","salvage","Keep richer classify_document_type rules and note/SQLite converters; default writer behavior differs."),("file-intelligence-hub","Nested independent job/worker/watch package","salvage","Preserve history; port only proven deltas."),("tools/file-intelligence-sources","Reference snapshot with provenance","keep","Keep as read-only reference."),("06_FIS_HTML","Paper identity/receipt HTML view","keep","Keep as presentation, not first-pass classifier."),("FIS PICS HTML","Prototype and active Simple FIS view","salvage","Preserve wired Simple and 5FIS/6FIS layout evidence."),("tools/fis-intelligence","CLI, MCP, index and Rust commands in one home","keep","Most complete integrated lookup tool, distinct from FIS registration."),("tools/fis/FIS-HTML-Intelligence","Identical index DB and three measured code files; connection notes differ","salvage","Retain distinct notes then retire verified duplicates after caller migration.")],
"B · Taggers":[("Theophysics_Tagger","Registry tagger and SQLite browse UI with optional watcher","keep","Strongest operating surface, catalog retains decisions."),("tools/filetagger","Lower-level file/folder/CHI taggers and math artefacts with a daemon","salvage","Use unique catalog/equation behavior, keep daemon disabled unless appointed."),("tools/file-intelligence-sources/snapshots/filetagger","Snapshot","keep","Six measured scripts equivalent after normalizing line endings.")],
"C · Organizers":[("tools/organize","Vendored pattern organizer plus Chi/rules/fallback and own organize.db","salvage","Adds rule-driven patterns and cross-drive inventory; retain seeds and integration notes."),("engine","Registry/admission, sidecar proposals and explicit rename/undo","keep","Different authority boundary; preserve imports."),("rule_brick","Questions/receipt gate only","keep","No write authority."),("10_FILE_ACTIONS","Object/folder organizing and batch previews","keep","Retain fast route and receipts."),("shared","Contracts and helpers","keep","Retain compatibility paths.")],
"D · Classifiers":[("03_CLASSIFY","MIM v1 YAML, validation/review and optional DeepSeek triage","keep","Primary review contract, centralize predictions outside v3."),("tools/organize/classifier.py","Chi rules, SQLite, LLM fallback","salvage","Candidate classifier/features; distinct schema."),("file-intelligence-system/fis_classifier.py","Folder, CHI/law/domain and doc-type results","salvage","Port local doc-type evidence."),("apps/classify/src/run.py","classification.v1 JSONL; Rust lexicon or Python FIS/Chi; optional Claude","keep","Make first pass SQLite-backed, explicit unresolved routing."),("10_FILE_ACTIONS/shared/deep_identify.py","JSON + file_cards/families/orphans CSV; scan_db adapter","keep","Keep independent evidence and improve registry link."),("10_FILE_ACTIONS/shared/glance_match.py","Page shape/terms/labels → CSV plus summary","salvage","Fast recognition evidence."),("10_FILE_ACTIONS/shared/apol_shadow.py","APOL shadow JSON; format/terms/boilerplate plus optional MiniLM","keep","Pilot evidence; do not automatically promote."),("10_FILE_ACTIONS/shared/attention_vector.py","TF-IDF signals and vector similarity","salvage","Use as independent local signal."),("10_FILE_ACTIONS/shared/lexicon_overlay.py","Lexicon scores on file cards","keep","Keep rule/source version explicit."),("10_FILE_ACTIONS/shared/atom_match.py","Claim overlap plus optional atom extraction","salvage","Bridge downstream; API stays explicit."),("10_FILE_ACTIONS/shared/series_finder.py","Series recognition/copy planning CSV and evidence","keep","Protected edits and user routing."),("10_FILE_ACTIONS/shared/series_aware_flatten.py","Series-aware flatten preview/apply routing","keep","Requires separate action authorization.")],
"E · Hubs":[("hub","Installed workers, notices and collection APIs","keep","Runtime authority, not file classification."),("folder_hub","Folder report/relay and read-only attached registry queries","keep","Use as thin read model."),("file-intelligence-hub","Worktree with overlapping runtime","salvage","native, runner, storage/db and cli differ by hash.")],
"F · Data":[("data","Contracts and tracked generated feeds","salvage","Separate generated output after consumer map."),("_data","Registry and stage receipts","keep","Maintain compatibility until location configuration exists."),(".data","Local workbook/tests/inventories/migration evidence","keep","Separate authoritative inputs from rebuildable outputs."),("10_FILE_ACTIONS/logs","6.98 GB matches output and sibling scan receipts","salvage","Conserve run provenance."),("runs","1.35 GB historical supervised runs","keep","Archive with metadata and rollback history.")],
"G · Lossless":[("_LOSSLESS_SUMMARY","Launcher, release scripts and examples","keep","Most complete base."),("LossLess/_LOSSLESS_SUMMARY","Second Lossless source","salvage","Namer differs; compare before retiring.")],
"H · GUI":[("step-3-combined-board.html","Three-pane combined mockup","keep","Best visual reference, no live integration claim."),("FIS PICS HTML/simple.html","Guided workflow and Prediction_GUI embedding","keep","Best current guided shell; external API path must move together."),("gui","Native FIS/scanner/review launchers","keep","Keep reachability and current edits."),("apps","Launcher/adapter set","keep","Preserve LAUNCH.bat behavior."),(PG,"Engine harness, approvals and actions","keep","Prediction and review owner.")],
"I · Root kits":[("files.zip","Original inventory kit","salvage","Archive as provenance."),("scripts.zip","Historical script and startup kit","salvage","Do not rerun or overwrite current launchers."),("tools/codex-script-hub","Recovered working launcher and utilities","keep","Retain configuration and provenance.")],
}

MOVES=[
("files.zip","archive/root-packages/files.zip","Archive the seven-member inventory kit beside its source history.","LOCAL"),
("scripts.zip","archive/root-packages/scripts.zip","Archive the 26-member package, including historical background installers.","LOCAL"),
("theophysics-read - Shortcut.lnk","archive/desktop-shortcuts/theophysics-read - Shortcut.lnk","Preserve the pointer; verify no shell workflow uses the repo-root shortcut.","LOCAL"),
("_BUILD_BRIEF_STAGE1_INVENTORY_REGISTRY.md","02_INVENTORY/docs/_BUILD_BRIEF_STAGE1_INVENTORY_REGISTRY.md","Store the Stage 1 brief with inventory.","LOCAL"),
("keyword_registry.json","03_CLASSIFY/reference/keyword_registry.json","Place the old keyword registry with classifying inputs after authority and consumer validation.","STRUCTURAL"),
("step-1-file-operations.html","06_FIS_HTML/reference/three-pane/step-1-file-operations.html","Preserve three related mockups together.","LOCAL"),
("step-2-destination.html","06_FIS_HTML/reference/three-pane/step-2-destination.html","Preserve three related mockups together.","LOCAL"),
("step-3-combined-board.html","06_FIS_HTML/reference/three-pane/step-3-combined-board.html","Keep the three-pane reference with its companion views.","LOCAL"),
("FIS PICS HTML/simple.html","06_FIS_HTML/views/simple.html","Stage the guided HTML only after protected edits and linked Prediction_GUI route are backed up and coordinated.","STRUCTURAL"),
("tools/fis/FIS-HTML-Intelligence/state/fis_html.sqlite","archive/duplicate-fis-html-index/fis_html.sqlite","Retire the exact duplicate only after consumers redirect and another snapshot-consistent hash check.","STRUCTURAL"),
("10_FILE_ACTIONS/logs/registry_find_20261112_020610_matches.csv","archive/file-action-receipts/registry_find_20261112_020610_matches.csv","Relocate the generated match CSV with its receipt and missing rows as a set.","STRUCTURAL"),
("10_FILE_ACTIONS/logs/registry_find_20261112_020610_summary.json","archive/file-action-receipts/registry_find_20261112_020610_summary.json","Keep the same run ID and adjust output paths in references, leaving original provenance in the receipt.","STRUCTURAL"),
("10_FILE_ACTIONS/logs/registry_find_20261112_020610_missing.csv","archive/file-action-receipts/registry_find_20261112_020610_missing.csv","Keep missing records with the same run ID.","LOCAL"),
]
BINDINGS={
"FIS PICS HTML/simple.html":[PG+r"\API\server.py SIMPLE_FIS; docs/FIS_STEP6_GUI.md; route /fis/simple; protect working edit before any move"],
"keyword_registry.json":["Verify authority and codebook aliases; compare with LEXICON_LOOKUP.json; do not assume they are equivalents"],
"tools/fis/FIS-HTML-Intelligence/state/fis_html.sqlite":["tools/fis/FIS-HTML-Intelligence/src/{cli,fis_html_index,fis_mcp_server}.py; CHAT2DB_CONNECT.md; external MCP config; rehash and inspect WAL before move"],
}
OLDER=[
(OLD+r"\file-intelligence-system\fis_vector_space.py","06_FIS_HTML/visualizations/fis_vector_space.py","One shared coordinate implementation for both renderers."),
(OLD+r"\file-intelligence-system\fis_visualizer.py","06_FIS_HTML/visualizations/fis_visualizer.py","Render cluster map from a registry adapter, not its own registry."),
(OLD+r"\file-intelligence-system\fis_meq_graph.py","06_FIS_HTML/visualizations/fis_meq_graph.py","Master Equation graph renderer; port documented CHI fields."),
(OLD+r"\file-intelligence-system\reports\FIS_CLUSTER_MAP.html","06_FIS_HTML/reference/FIS_CLUSTER_MAP.html","Preserve historical evidence view; current FIS Library can link to it."),
(OLD+r"\file-intelligence-system\reports\FIS_MEQ_GRAPH.html","06_FIS_HTML/reference/FIS_MEQ_GRAPH.html","Paired evidence view; preserve chart metadata."),
(V1+r"\file-intelligence-system\INSTALL_SENDTO.bat","tools/fis/reference/sendto/INSTALL_SENDTO.bat","Reference for installing the Send To integration, requires explicit installation authority."),
(V1+r"\file-intelligence-system\FIS_Index_Folder.bat","tools/fis/reference/sendto/FIS_Index_Folder.bat","Reference wrapper tied to older writer; rebind to approved FIS CLI before use."),
(OLD+r"\file-intelligence-system\RUN_SCAN_CHAIN_2.ps1","02_INVENTORY/reference/RUN_SCAN_CHAIN_2.ps1","Sequential scan and single-writer rationale; keep historical roots, port a root-configured batch."),
(OLD+r"\file-intelligence-system\approval-gui\index.html",PG+r"\gui\reference\legacy-fis-approval.html","Preserve toast-to-HTML design reference; do not use the older server as a second authority."),
(OLD+r"\file-intelligence-system\approval-gui\fis_decisions.jsonl",PG+r"\data\imports\legacy-fis\fis_decisions.jsonl","Potential evaluation data. Resolve recurring proposal IDs and distinguish edits from acceptance before training."),
]
ROOT_FILES=[
("files.zip","Seven entries including run.py, BATCH_ALL, inventory_core and launchers.","archive/root-packages"),
("scripts.zip","26 entries including scripts/fis startup setup.","archive/root-packages"),
("step-1-file-operations.html","Operations-first mockup.","06_FIS_HTML/reference/three-pane"),
("step-2-destination.html","Destination mockup.","06_FIS_HTML/reference/three-pane"),
("step-3-combined-board.html","Operations/workbench/targets composition.","06_FIS_HTML/reference/three-pane"),
("theophysics-read - Shortcut.lnk",r"Windows pointer to C:\Users\David\theophysics-read, which exists.","archive/desktop-shortcuts"),
("keyword_registry.json","Legacy keyword data, relationship to the 536-term lexicon not verified.","03_CLASSIFY/reference, after authority check"),
("_BUILD_BRIEF_STAGE1_INVENTORY_REGISTRY.md","Stage 1 design brief.","02_INVENTORY/docs"),
("LAUNCH.bat","Lists apps/* relative to repo root, invokes app wrappers.","Keep at root"),
("README.md","Repository navigation and installed commands.","Keep at root"),
("pyproject.toml / uv.lock","Package entry points and lock, pyproject currently protected.","Keep at root"),
(".gitignore","Controls local state visibility.","Keep at root"),
]
QUESTIONS=[
"Should fis/ become the one first-pass FIS package, with existing document-type and lookup tools behind adapters?",
"Do you want the desktop to have a separate registry instance even when it sits on the same physical drive as an existing registry?",
"Which exact file is the approved CLASSIFICATION_TAXONOMY_v2.json and how should its ten axes map to the 11 found in the Rust configuration?",
"May a series candidate display a provisional code before the registry issues a numeric S####, provided it cannot enter a filename?",
"Which residents are currently appointed? Does the October FIS sign-in appointment still apply?",
"Which separate Rust checkout owns intake, canon, enrich and assemble?",
"May the older decisions be used for separate shadow evaluation after proposal IDs and name edits are reconciled?",
"Should Simple FIS and the three-pane board be the two reference views with approvals delegated to Prediction_GUI?",
"Do you want external Chat2DB and Send To pointers redirected before the identical HTML SQLite copy is retired?",
"Which exact Nov 8 identity document should the v3 registry cite?",
"Is C:\\Theophysics_Tagger the intended older tagger path, or should another original be audited?",
"Should older recovery worktrees remain cold references after their unique working pieces are copied?",
"Can the 6.98 GB scan output trio move together after its exact consumers and recovery receipt are checked?",
]
def assemble():
 inv=json.loads((A/"inventory_raw.json").read_text())
 meta=rows("file_metadata.csv")
 ref=rows("source_references.csv")
 launcher=rows("launchers.csv")
 boundary=rows("scan_boundaries.csv")
 excluded=rows("content_exclusions.csv")
 hashes=json.loads((A/"hash_comparisons.json").read_text())
 tracked_big=rows("tracked_over_5mb.csv")
 imports,dependents,bindings=defaultdict(set),defaultdict(set),defaultdict(set)
 for r in ref:
  src=r["source"].split("/")[0]
  if r["kind"]=="cross-folder import":
   for t in r["candidate_targets"].split(" | "):
    dst=t.split("/")[0]
    if dst!=src: imports[src].add(dst);dependents[dst].add(src)
  val=(r["value"]+" "+r["candidate_targets"]).replace("\\","/").casefold()
  for source,_,_,_ in MOVES:
   if Path(source).name.casefold() in val:bindings[source].add(r["source"]+":"+r["line"])
 for r in launcher:
  for source,_,_,_ in MOVES:
   if Path(source).name.casefold() in r["command_excerpt"].casefold():
    bindings[source].add(r["source"]+":"+r["line"])
 for r in inv:
  n=r["folder"]
  role=("Generated","junk","Test-run cache or scratch results; no application entry point detected.") if n.startswith(".pytest") else FOLDERS.get(n,("Tooling","unknown","Ownership remains a question."))
  r.update(dict(zip(("group","status","role"),role)))
  r["confidence"]="VERIFIED source and metadata; runtime activation not tested"
  r["provisional_imports"]=sorted(imports[n]);r["provisional_dependents"]=sorted(dependents[n])
 inv.sort(key=lambda r:(r["group"],r["folder"].casefold()))
 (A/"inventory.json").write_text(json.dumps(inv,indent=2,ensure_ascii=False),encoding="utf-8")
 moves=[]
 omitted=[]
 for source,dest,reason,reach in MOVES:
  if not (ROOT/source).is_file() or (ROOT/dest).exists():
   omitted.append((source,dest,"Missing input or occupied destination; omitted from the executable list."))
   continue
  found=[*BINDINGS.get(source,[]),*sorted(bindings[source])]
  hints="; ".join(found) or "No matching static path found; verify external shortcuts and scripts."
  moves.append((str(ROOT/source),str(ROOT/dest),reason,"VERIFIED",reach,hints))
 save("move_plan.csv",["from","to","reason","confidence","reach","references_to_update"],moves)

 duplicates=[]
 for cluster,members in CLUSTERS.items():
  for path,role,decision,note in members:
   duplicates.append((cluster,path,"Verified functional/source signature (no byte equality claimed)",decision,role+" · "+note))
 for match in hashes:
  if "a_sha" not in match:continue
  a,b=match["a"],match["b"]
  cluster="A · FIS" if "fis-intelligence" in a else "B · Taggers" if "filetagger" in a else "G · Lossless"
  second="retire" if b.endswith("state/fis_html.sqlite") else "salvage" if match["comparison"]=="different" else "keep"
  duplicates.extend([(cluster,a,match["a_sha"],"keep",match["comparison"]+" with "+b),
                     (cluster,b,match["b_sha"],second,match["comparison"]+" with "+a)])
 save("duplicates.csv",["cluster","path","hash_or_signature","keep|retire|salvage","note"],duplicates)
 oldcmp=json.loads((ROOT/".data/migrate_compare/by_folder.json").read_text())
 ref_counts=Counter(r["kind"] for r in ref)
 end_path=A/"end_summary.json"
 closing=json.loads(end_path.read_text(encoding="utf-8")) if end_path.exists() else {}
 return inv,meta,ref_counts,launcher,boundary,excluded,hashes,tracked_big,moves,omitted,duplicates,oldcmp,closing

def render():
 inv,meta,refcounts,launcher,boundary,excluded,hashes,big,moves,omitted,duplicates,old,closing=assemble()
 pull=(A/"git_pull.txt").read_text(encoding="utf-8-sig").strip()
 verdict='<header id="s1"><div class="intro">DAVID-OSv3 · READ-ONLY AUDIT</div><h1>Set the owners before moving the folders</h1>'
 verdict+=p("November 14, 2026 · combine/fis-into-david-os · "+(A/"head_after_pull.txt").read_text(encoding="utf-8-sig").strip()[:7]+" · "+pull.replace("\n"," · "))
 verdict+=p("Overall health: strong tools and useful evidence, but no single first-pass owner or consistent handoff between registry, classification and approval. The reviewed judgments below are VERIFIED by code, observed fixtures or hash comparison. Runtime behavior was not tested.")
 stats=[(len(meta),"file paths"),(len(inv),"top-level folders"),(len(STRUCTURAL),"structural findings"),(len(moves),"proposed moves")]
 verdict+='<div class="stats">'+''.join('<span><strong>'+f'{n:,}'+'</strong>'+esc(l)+'</span>' for n,l in stats)+'</div>'
 verdict+='<ol class="verdict">'+''.join('<li><strong>'+esc(title)+'</strong> '+esc(text)+'</li>' for title,text,_ in STRUCTURAL)+'</ol>'
 verdict+=p("Three changes first: name the standalone FIS owner; make per-drive SQLite and identity issuance explicit; let Prediction_GUI own predictions and approvals through stable adapters.")+'</header>'
 titles=["Layout","Folders","Duplicates","Proposed moves","Breakage","Principles","Git hygiene","Older sources","Questions"]
 nav='<nav>'+''.join(f'<a href="#s{i}">{esc(label)}</a>' for i,label in enumerate(titles,2))+'</nav>'
 output=[verdict,nav]
 groups=defaultdict(list)
 for row in inv: groups[row["group"]].append(row)
 view='<div class="flow">'+''.join('<article><h3>'+esc(group)+'</h3>'+''.join(
  '<span class="pill '+esc(item["status"])+'">'+esc(item["folder"])+'</span>' for item in entries)+'</article>' for group,entries in groups.items())+'</div>'
 output.append(section(2,"Current layout",p("Green: live implementation or consumer evidence. Amber: retained reference/stale. Blue: overlapping or duplicate. Gray: generated. Live means a launch or consumer exists in the code, not that a process is running.")+view))
 body=p("Sizes count observed paths, including metadata in excluded trees. Last change is the newest leaf-file mtime. Imports below are static candidates, and do not establish live dependency.")
 for r in inv:
  body+=details(f'{r["folder"]} · {r["file_count"]:,} files · {r["size_bytes"]/1e6:,.2f} MB',
    p(r["role"])+table(["Status","Last leaf change","Tracked","Skipped content files"],
    [(r["status"],r["last_change"] or "Not observed",r["tracked_files"],r["excluded_content_files"])])+
    p("Possible imports: "+(", ".join(r["provisional_imports"]) or "none resolved across top-level folders")+
       " · possible dependents: "+(", ".join(r["provisional_dependents"]) or "none resolved across top-level folders"))+
    (table(["Entry point","Kind","Git state"],[(e["path"],e["kind"],e["git"]) for e in r["entry_points"][:9]]) if r["entry_points"]
      else p("No main/launcher detected in eligible code; see role and dependency notes."))+
    (p(f'{len(r["entry_points"])} entries in inventory.json.') if len(r["entry_points"])>9 else ""))
 body+='<h3>Loose root files</h3>'+table(["File","Observed role","Proposed destination"],ROOT_FILES)
 output.append(section(3,"Folder by folder",body+links("inventory.json","file_metadata.csv")))

 body=""
 for cl, members in CLUSTERS.items(): body+='<h3>'+esc(cl)+'</h3>'+table(["Member","Observed role","Disposition","Retain or salvage"],members)
 body+=details("Verified hash comparisons",table(["First path","Second path","Result","Bytes A / B"],[
  (r["a"],r["b"],r["comparison"],str(r.get("a_bytes","—"))+" / "+str(r.get("b_bytes","—"))) for r in hashes]))
 output.append(section(4,"Duplicate and overlapping clusters",body+links("duplicates.csv","hash_comparisons.json")))
 lanes=("01_PROFILE · Onboard selected roots","02_INVENTORY · Registry and ID issuer","03_CLASSIFY · Standalone FIS / local rules → MiniLM → explicit DeepSeek",
        "04_ADAPT · Versioned adapters","05_TOPIC_COLLECTION · Downstream boundary","06_FIS_HTML · Folder/receipt views","10_FILE_ACTIONS · Approved execution and recovery")
 body='<div class="flow">'+''.join('<article>'+esc(x)+'</article>' for x in lanes)+'</div>'
 body+=p("Keep existing package import and launcher paths until forwarding wrappers and hash tests pass. Keep 07–09 vacant. Run the separate Rust content engine after the FIS registration boundary. Host configuration selects one registry per drive plus desktop. Code, schemas and compact fixtures stay tracked; operational SQLite, scratch exports and receipts have explicit data roots; cold archives stay out of scans.")
 body+=p("Every row below is a verified-path proposal, not approval to execute. For the Simple FIS HTML coordinate with the author first. For SQLite, redirect consumers, quiesce writers and rehash a consistent copy. Keep the stage 10 run outputs together.")
 body+=table(["From","To","Reason","Confidence","Reach","References to update"],moves)
 if omitted:body+=table(["Candidate source","Destination","Gate"],omitted)
 output.append(section(5,"Proposed structure and exact move list",body+links("move_plan.csv")))

 body=p(f"Indexed {refcounts['absolute literal']:,} drive/LAN literals and {refcounts['cross-folder import']:,} cross-folder import observations, plus {len(launcher):,} launcher lines. These include absolute D:, H:, Z:, C:\\Users and \\\\192.168 forms, and many repeated generated links. Import resolution is static; candidate targets may be ambiguous.")
 body+=table(["Binding","Breakage to avoid"],[
 ("Root launch","LAUNCH.bat discovers apps/*; leave it in place and preserve each selected app launcher."),
 ("Registry","engine.registry and stage2b_common expect _data/registry.sqlite. Stage 2 approvals and file mutations depend on admission data."),
 ("Simple FIS","Prediction_GUI/API/server.py uses a fixed sibling path; original guided actions still target 127.0.0.1:61845. Check both boundary contracts."),
 ("Index + MCP","Duplicate HTML index paths and Chat2DB endpoint/setup notes can be referenced outside the repo."),
 ("Scan receipts","Move all three registry-find artifacts together; summary paths, historical links and recovery receipts are dependencies."),
 ("Windows services","Existing startup task/Send To pointers may bear absolute paths; the audit did not invoke installers or inspect unrelated settings."),
 ])
 body+=p(f"Content scope: UTF-8/UTF-16 source/config/docs in the collector’s extension list up to 20 MiB. {len(boundary)} metadata boundaries, {len(excluded)} oversized/unreadable text exclusions. Binary and generated CSV/JSONL files are counted but not searched for code references. Unknown dynamic bindings are not claimed complete.")
 output.append(section(6,"Breakage map",body+links("source_references.csv","launchers.csv","scan_boundaries.csv","content_exclusions.csv")))

 body=table(["Finding","Reach","Confidence","Evidence"],[(n,"STRUCTURAL","VERIFIED",t+" · "+ev) for n,t,ev in STRUCTURAL])
 body+=table(["Specific check","Reach","Confidence","Observed result"],[
 ("First-pass SQLite","STRUCTURAL","VERIFIED","Direct stage/runtime launchers and classification.v1 export can bypass a central per-drive admission boundary. Export formats should be projections of recorded results."),
 ("Stored identity","STRUCTURAL","VERIFIED","Rule Brick UUIDv4 identifiers and rename changesets are internal. A rule to prohibit UUIDs in actual filenames must inspect producer output separately; absence was not claimed."),
 ("Classification truth","STRUCTURAL","VERIFIED","MASTER_CLASSIFICATION_SHEET.xlsx has 25 series family and 179 registry map rows excluding headers. LEXICON_LOOKUP has 536 keys. The Rust classification_2_0.json has 11 names under axes, including chi_primary and chi_secondary; the exact alternate 10-axis filename was not located."),
 ("An appointed resident","STRUCTURAL","VERIFIED receipt","October 25 FIS receipt lists a sign-in task and tray supervisor. Other native/poll watchers, watcher launchers, standalone FIS background, legacy tagger daemon and clipboard loops are indexed. Current permission applies per resident."),
 ("Separate Rust content","STRUCTURAL","VERIFIED source scope","Found Rust fingerprint, lexicon, and FIS-kernel pieces, plus Python downstream helpers. None alone establishes authority over intake/canon/enrich/assemble; external ownership needs a ruling."),
 ("Legacy folder note","LOCAL","VERIFIED","Standalone HTML can embed legacy notes byte-for-byte; old folder-memory still supports .fisnote generation. Use compatibility conversion and explicitly choose the writer before replacing notes."),
 ("ZIP snapshots","INERT","VERIFIED","Root packs contain historical components; dependency observations are limited to the indexed paths.")
 ])
 output.append(section(7,"Principle checks",body+links("principle_signals.csv")))

 body=table(["Tracked and over 5 MB","Working-tree bytes"],[(r["path"],f'{int(r["bytes"]):,}') for r in big])
 body+=p("Measured git ls-files entries against the working tree, threshold 5,000,000 bytes. Ignoring files does not untrack them. Keep the GUI catalog until its lineage and consumers are resolved.")
 body+=table(["Treatment","Files"],[
 ("Rebuildable when closed", "__pycache__, *.pyc, .pytest_* scratch, and generated package metadata. Recreate .venv only when no current launcher uses it."),
 ("Preserve and archive", "Root ZIPs, legacy sidecar archive, verified duplicate SQLite plus WAL context, dated recovery receipts and large generated logs."),
 ("Keep", ".git, working contracts and launchers, active registries, reviewed sources and all pre-existing edits."),
 ])
 body+='<pre>'+esc(".pytest_*/\n10_FILE_ACTIONS/logs/\n06_FIS_HTML/out/\n06_FIS_HTML/receipts/\n**/__pycache__/\n*.sqlite-shm\n*.sqlite-wal\n# After ownership checks and untracking approval:\n/gui/catalog.db\n/data/rename/rename-proposal.v1.jsonl")+'</pre>'
 if closing:
  body+=p("Start/end Git porcelain outside _AUDIT identical: "+str(closing["git_unchanged"])+". "+closing["scope"])
  if closing["changed"]:body+=table(["Observed outside _AUDIT","Change"],[(r["path"],r["change"]) for r in closing["changed"][:35]])
 body+=links("git_pull.txt","git_status_start.txt","git_status_end.txt","end_summary.json","tracked_over_5mb.csv")
 output.append(section(8,"Junk and Git hygiene",body))

 n=sum(d["files"] for d in old.values());hit=sum(d["already_in_v3"] for d in old.values())
 body=p(f"Reused the previous by_folder.json and unique_files.tsv. In that comparison’s scope: {n:,} entries, {hit:,} already in v3 and {n-hit:,} absent. No rehash of the old tree was performed. These are the comparison’s counts, not a claim of full corpus coverage.")
 body+=table(["Older location","What was checked"],[
 (OLD,"Selected tools, source code and recovered approval queue. ZZZ and salvage archives retained."),
 (V1,"Original monorepo. Matched named FIS tooling and installers."),
 (r"D:\GitHub\David-OS-v2-source","Top-level and targeted filename lookup."),
 (r"D:\GitHub\David-OSv3-fi","Top-level and targeted filename lookup."),
 (r"H:\_DAVID_OS_RECOVERY","Recovery root found, targeted filename lookup only."),
 (r"\\192.168.2.50\h_hp\Desktop","Top-level listing only; no NAS subtrees scanned."),
 ])
 body+=table(["Source","Proposed copy/port destination","Reason","Confidence"],
  [(s,d if re.match(r"^[A-Za-z]:",d) else str(ROOT/d),why,"VERIFIED source present" if Path(s).is_file() else "INFERRED; verify path") for s,d,why in OLDER])
 body+=p("These older-source items are proposals to copy or port, separate from move_plan.csv.")
 output.append(section(9,"Missing or better in older copies",body))
 output.append(section(10,"Questions for David",'<ul>'+''.join('<li>'+esc(x)+'</li>' for x in QUESTIONS)+'</ul>'))
 style="""*{box-sizing:border-box}body{margin:0;background:#101b23;color:#ecf4f4;font:16px/1.55 system-ui,sans-serif}main{max-width:1430px;margin:auto;padding:22px}h1{font-size:clamp(36px,4.3vw,61px);line-height:1.05;letter-spacing:-.035em;margin:8px 0 16px}h2{font-size:26px;margin:0 0 12px}p{max-width:115ch}a{color:#a4eedb}header,section{background:#172832;border:1px solid #35505b;border-radius:14px;padding:20px;margin:16px 0}nav{display:flex;flex-wrap:wrap;gap:16px;padding:13px}.intro{color:#a4eedb;font-size:12px;font-weight:750;letter-spacing:.12em}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.stats span{background:#0f2028;padding:8px 10px;border-radius:7px}.stats strong{display:block;font-size:22px}.verdict{columns:2;column-gap:34px}.verdict li{break-inside:avoid;padding-bottom:8px}.flow{display:flex;gap:9px;overflow:auto}.flow article{min-width:155px;background:#0f2028;border-radius:7px;padding:9px}.pill{display:block;border-radius:4px;padding:3px 6px;margin:4px 0;overflow-wrap:anywhere}.live{background:#1f5146}.stale{background:#5a4828}.duplicate{background:#284e65}.junk{background:#3e454a}details{background:#12232a;border:1px solid #35505b;border-radius:8px;padding:8px 12px;margin:7px 0}summary{cursor:pointer;font-weight:650}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #35505b;padding:8px;overflow-wrap:anywhere}th{background:#213e4a}td{max-width:60ch}pre{background:#12232a;padding:12px;white-space:pre-wrap}@media(max-width:780px){.verdict{columns:1}.stats{grid-template-columns:1fr 1fr}main{padding:9px}}"""
 report=A/"DAVID_OSV3_AUDIT_2026-11-14.html"
 report.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>David-OSv3 audit</title><style>'+style+'</style><main>'+''.join(output)+'</main></html>',encoding="utf-8")
 print(report, len(moves), "proposed moves;",len(duplicates),"duplicate rows;",len(inv),"folder cards", flush=True)

if __name__=="__main__":
 render()
