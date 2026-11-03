"""
fis_namer.py — Compressed name generator + auto-approver for FIS.

Naming format:
    DOMAIN__CT__tag1-tag2[-tag3]__YYYYMMDD__ST.ext

All fields are short codes.  Nothing spelled out.
- DOMAIN  2 letters  — knowledge domain
- CT      3 letters  — content type (what the file IS)
- tags    2-3 codes  — topic signals, domain-specific
- date    8 digits   — YYYYMMDD from file mtime
- ST      2 letters  — lifecycle status

Auto-approval:
    confidence >= AUTO_APPROVE_THRESHOLD  →  approve immediately
    confidence in [QUEUE_THRESHOLD, AUTO)  →  put in approval queue
    confidence < QUEUE_THRESHOLD           →  skip (too uncertain)
"""

import re
import time
from datetime import datetime
from pathlib import Path

try:
    from fis_preference_engine import get_engine as _get_pref_engine
    PREF_ENGINE_OK = True
except ImportError:
    PREF_ENGINE_OK = False
    def _get_pref_engine(): return None

try:
    from fis_enricher import maybe_enrich as _maybe_enrich
    ENRICHER_OK = True
except ImportError:
    ENRICHER_OK = False
    def _maybe_enrich(result, rec, db_path): return result

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

AUTO_APPROVE_THRESHOLD = 0.72   # approve without asking
QUEUE_THRESHOLD        = 0.45   # below this → don't even propose a name

# ---------------------------------------------------------------------------
# Domain codes  (2 letters)
# ---------------------------------------------------------------------------

DOMAIN_CODES = {
    # science / philosophy
    "theophysics":    "TH",
    "theology":       "TH",
    "physics":        "PH",
    "epistemology":   "EP",
    "consciousness":  "CS",
    "metaphysics":    "MT",
    "morality":       "MR",
    "information":    "IF",
    # applied / work
    "code":           "CD",
    "data":           "DT",   # overridden to DT=DayTrading below by context
    "media":          "MD",
    "document":       "GN",   # generic doc
    # specific domains David uses
    "trading":        "TR",
    "legal":          "LG",
    "knowledge":      "KG",
    "evidence":       "EV",
    "ai":             "AI",
    "general":        "GN",
}

# Keyword hints that override the domain classifier toward a specific code
DOMAIN_KEYWORD_HINTS: list[tuple[list[str], str]] = [
    (["theophysics","theophys","logos","chi","law0","law1","coherence","falsif"], "TH"),
    (["premarket","backtest","watchlist","ticker","pnl","options","day trad","trade log"], "DT"),
    (["physics","quantum","entropy","relativity","string theory","particle"], "PH"),
    (["sermon","congregation","homily","preach","scripture","gospel"], "TH"),
    (["python","javascript","typescript","fastapi","autohotkey","ahk","node","react"], "CD"),
    (["legal","contract","clause","statute","litigation","attorney"], "LG"),
    (["knowledge graph","graphify","axiom","claim","corpus"], "KG"),
    (["evidence","audit","statistical","claim","falsifiable","peer-review"], "EV"),
]

def resolve_domain(chi_domain: str, name: str, path: str = "") -> str:
    """Pick the best 2-letter domain code using filename + folder path as hints."""
    text = (name + " " + path).lower()
    for keywords, code in DOMAIN_KEYWORD_HINTS:
        if any(k in text for k in keywords):
            return code
    return DOMAIN_CODES.get((chi_domain or "").lower(), "GN")

# ---------------------------------------------------------------------------
# Content-type codes  (3 letters)
# ---------------------------------------------------------------------------

CT_CODES = {
    "document": "DOC",
    "code":     "COD",
    "data":     "DAT",
    "note":     "NOT",
    "config":   "CFG",
    "proof":    "PRF",
    "paper":    "PAP",
    "sermon":   "SRM",
    "image":    "IMG",
    "video":    "VID",
    "audio":    "AUD",
    "binary":   "BIN",
    "file":     "BIN",
}

def resolve_ct(content_type: str) -> str:
    return CT_CODES.get((content_type or "").lower(), "DOC")

# ---------------------------------------------------------------------------
# Status codes  (2 letters)
# ---------------------------------------------------------------------------

STATUS_CODES = {
    "draft":   "DR",
    "active":  "AC",
    "final":   "FN",
    "archive": "AR",
    "review":  "RV",
    "wip":     "WP",
}

def resolve_status(name: str, mtime: float) -> str:
    """Infer lifecycle status from filename patterns and age."""
    low = name.lower()
    if any(k in low for k in ("draft","wip","temp","tmp","working","scratch")):
        return "DR"
    if any(k in low for k in ("final","done","complete","publish","release")):
        return "FN"
    if any(k in low for k in ("archive","old","backup","bak","_old","_bak","deprecated")):
        return "AR"
    if any(k in low for k in ("review","check","todo","pending","flag")):
        return "RV"
    # age-based: anything not touched in 6 months → archive
    age_days = (time.time() - mtime) / 86400 if mtime else 0
    if age_days > 180:
        return "AR"
    return "AC"

# ---------------------------------------------------------------------------
# Tag abbreviation table  (2-4 letters)
# Topics the system compresses so they never need to be spelled out in a name.
# ---------------------------------------------------------------------------

TAG_ABBREVS: list[tuple[list[str], str]] = [
    # --- Theophysics / theology ---
    (["consciousness","aware","sentien"],          "CSN"),
    (["coherence","coher"],                        "COH"),
    (["falsif","refut","disproof"],                "FSL"),
    (["chi factor","chi-factor","χ"],              "CHI"),
    (["grace","agape","shalom"],                   "GRC"),
    (["moral","virtue","fruit","anti-fruit"],       "MRL"),
    (["entropy","disorder","decay"],               "ENT"),
    (["faith","belief","trust"],                   "FTH"),
    (["relation","bond","covenant"],               "REL"),
    (["quantum","superposit"],                     "QNT"),
    (["knowledge","epistem","truth"],              "KNW"),
    (["time","kairos","temporal","chronos"],       "TMP"),
    (["logos","word","scripture"],                 "LGS"),
    (["law01","l01","gravity"],                    "L01"),
    (["law02","l02","motion","inertia"],           "L02"),
    (["law03","l03","entropy"],                    "L03"),
    (["law04","l04","love","strong force"],        "L04"),
    (["law05","l05","wave","light","radiation"],   "L05"),
    (["law06","l06","information","logos"],        "L06"),
    (["law07","l07","identity","image"],           "L07"),
    (["law08","l08","covenant","relation"],        "L08"),
    (["law09","l09","redemption","healing"],       "L09"),
    (["law10","l10","omega","telos","end"],        "L10"),
    # --- Day trading / finance ---
    (["premarket","pre-market","pre market"],      "PMK"),
    (["backtest","back-test","back test"],         "BKT"),
    (["watchlist","watch list"],                   "WTL"),
    (["risk","stop loss","drawdown"],              "RSK"),
    (["strategy","strat","setup"],                 "STG"),
    (["signal","indicator","alert"],               "SIG"),
    (["profit","pnl","p&l","return"],              "PNL"),
    (["options","calls","puts","expiry"],          "OPT"),
    (["scanner","screener"],                       "SCN"),
    (["journal","trade log","entry log"],          "JRN"),
    (["chart","candlestick","ohlc"],               "CHT"),
    # --- Code / dev ---
    (["daemon","background","service","worker"],   "DMN"),
    (["server","fastapi","flask","api"],           "SRV"),
    (["classifier","classify","classify"],         "CLF"),
    (["database","sqlite","db","schema"],          "DBS"),
    (["config","setting","json","yaml"],           "CFG"),
    (["autohotkey","ahk",".ahk"],                 "AHK"),
    (["html","css","frontend","ui","web"],         "WEB"),
    (["installer","install","setup","bat"],        "INS"),
    (["watcher","watchdog","observer","event"],    "WCH"),
    # --- Evidence / research ---
    (["statistical","statistic","sigma"],          "STA"),
    (["audit","review","check","verify"],          "AUD"),
    (["claim","assertion","proposition"],          "CLM"),
    (["axiom","axioms","foundational"],            "AXM"),
    (["corpus","corpora","dataset","training"],    "CRP"),
    (["graph","knowledge graph","graphify"],       "GRP"),
    (["proof","proven","qed","theorem","lemma"],   "PRF"),
    # --- Media ---
    (["screenshot","screen shot","screen-shot"],    "SCR"),
    (["thumbnail","thumb","preview"],              "THM"),
    (["recording","recorded","rec"],               "REC"),
    (["export","exported","render"],               "EXP"),
]

def extract_tags(name: str, sample: str = "", domain_code: str = "GN", max_tags: int = 3) -> list[str]:
    """Return up to max_tags tag codes from filename + sample text."""
    text = (name + " " + sample).lower()
    seen: set[str] = set()
    tags: list[str] = []
    for keywords, code in TAG_ABBREVS:
        if code in seen:
            continue
        if any(k in text for k in keywords):
            seen.add(code)
            tags.append(code)
            if len(tags) == max_tags:
                break
    return tags

# ---------------------------------------------------------------------------
# Slug builder — extract a short human topic from the filename
# ---------------------------------------------------------------------------

_STRIP = re.compile(r"[_\-\s]+")
_JUNK  = re.compile(
    r"\b(v\d+|final|copy|old|new|temp|tmp|test|draft|bak|backup"
    r"|untitled|document|file|data|the|and|for|with|from|this|that)\b",
    re.I,
)

def _topic_slug(name: str, max_words: int = 4) -> str:
    """Turn a filename into a short kebab-case topic slug."""
    stem = Path(name).stem
    stem = _JUNK.sub("", stem)
    words = _STRIP.split(stem.strip())
    words = [w.lower() for w in words if len(w) > 2][:max_words]
    return "-".join(words) if words else "untitled"

# ---------------------------------------------------------------------------
# Main name generator
# ---------------------------------------------------------------------------

def propose_name(rec: dict, db_path: str = "") -> dict:
    """
    Given a file DB record (with classification fields), return:
    {
        "proposed_name": "TH__NOT__CSN-COH__20260627__DR.md",
        "domain_code":   "TH",
        "ct_code":       "NOT",
        "tags":          ["CSN", "COH"],
        "status_code":   "DR",
        "date_str":      "20260627",
        "decision":      "auto_approve" | "queue" | "skip",
        "reason":        "confidence 0.87 >= threshold 0.72",
    }
    """
    name    = rec.get("name", "")
    ext     = (rec.get("ext") or Path(rec.get("path","")).suffix).lower()
    mtime   = rec.get("mtime") or 0.0
    conf    = rec.get("chi_confidence") or 0.0

    ct_code     = resolve_ct(rec.get("content_type",""))
    ext_known   = ct_code not in ("DOC", "BIN") or ext in {
        ".pdf",".docx",".doc",".xlsx",".xls",".csv",".json",".md",".txt",
        ".py",".js",".ts",".html",".yaml",".yml",".png",".jpg",".mp4",".mp3",
    }

    # Skip only if BOTH confidence is low AND extension is unrecognised
    if conf < QUEUE_THRESHOLD and not ext_known:
        return {"decision": "skip", "reason": f"confidence {conf:.2f} and unknown ext {ext}"}

    domain_code = resolve_domain(rec.get("chi_domain",""), name,
                                  rec.get("path",""))
    status_code = resolve_status(name, mtime)
    tags        = extract_tags(name, rec.get("sample",""), domain_code)
    date_str    = datetime.fromtimestamp(mtime).strftime("%Y%m%d") if mtime else "000000"

    tag_str  = "-".join(tags) if tags else "GN"
    proposed = f"{domain_code}__{ct_code}__{tag_str}__{date_str}__{status_code}{ext}"

    # Build the proposal dict (needed for preference engine)
    proposal = {
        "proposed_name": proposed,
        "domain_code":   domain_code,
        "ct_code":       ct_code,
        "status_code":   status_code,
        "tags":          tags,
    }

    # Content types certain from extension alone (no text reading needed)
    ext_certain = ext in {
        ".py",".js",".ts",".jsx",".tsx",".ahk",
        ".json",".csv",".sqlite",".db",
        ".md",".txt",
        ".png",".jpg",".jpeg",".gif",".webp",".svg",
        ".mp4",".mov",".avi",".mkv",
        ".mp3",".wav",".flac",".aac",
    }

    # Ask preference engine first (it blends raw conf + learned patterns)
    engine = _get_pref_engine() if PREF_ENGINE_OK else None
    if engine and engine.n_seen >= engine.MIN_SAMPLES:
        ok, reason = engine.should_auto_approve(proposal, conf, AUTO_APPROVE_THRESHOLD)
        decision   = "auto_approve" if ok else "queue"
    elif conf >= AUTO_APPROVE_THRESHOLD or ext_certain:
        decision = "auto_approve"
        reason   = (f"conf={conf:.2f}>={AUTO_APPROVE_THRESHOLD}"
                    if conf >= AUTO_APPROVE_THRESHOLD else "ext-certain")
    else:
        decision = "queue"
        reason   = f"conf={conf:.2f} below threshold"

    result = {
        "proposed_name": proposed,
        "domain_code":   domain_code,
        "ct_code":       ct_code,
        "tags":          tags,
        "status_code":   status_code,
        "date_str":      date_str,
        "decision":      decision,
        "reason":        reason,
        **proposal,
    }

    # Below LOW_CONF_THRESHOLD → enrich from similar approved files before queueing
    if ENRICHER_OK and db_path and (rec.get("chi_confidence") or 0.0) < 0.50:
        result = _maybe_enrich(result, rec, db_path)

    return result


# ---------------------------------------------------------------------------
# Batch auto-approver — call this after first crawl pass
# ---------------------------------------------------------------------------

def run_auto_approve(db_path: str, dry_run: bool = False) -> dict:
    """
    Scan fis_catalog.db, generate names for all classified files,
    auto-approve high-confidence ones, queue the rest.
    Every auto-approve feeds the preference engine so it learns immediately.
    Returns summary counts.
    """
    import sqlite3

    engine = _get_pref_engine() if PREF_ENGINE_OK else None

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    c = con.cursor()

    # ensure columns exist
    existing = {r[1] for r in c.execute("PRAGMA table_info(files)").fetchall()}
    for col, defn in [("proposed_name","TEXT"), ("approved","INTEGER"), ("approval_note","TEXT")]:
        if col not in existing:
            c.execute(f"ALTER TABLE files ADD COLUMN {col} {defn}")
    con.commit()

    rows = c.execute("""
        SELECT rowid, path, name, ext, mtime, chi_domain, content_type,
               chi_confidence, chi_json, folder_class, status
        FROM files
        WHERE classified_at IS NOT NULL
          AND (approved IS NULL)
          AND status = 'active'
        ORDER BY chi_confidence DESC
    """).fetchall()

    counts = {"auto_approved": 0, "queued": 0, "skipped": 0, "total": len(rows)}

    for row in rows:
        rec      = dict(row)
        result   = propose_name(rec, db_path=db_path)
        decision = result["decision"]

        if dry_run:
            tag  = decision.upper()[:4]
            name = rec["name"] + (rec["ext"] or "")
            prop = result.get("proposed_name", "—")
            print(f"  [{tag:4s}] {name:<40s} -> {prop}")
            counts[{"auto_approve":"auto_approved"}.get(decision, decision)] += 1
            continue

        if decision == "auto_approve":
            c.execute(
                "UPDATE files SET proposed_name=?, approved=1, approval_note=? WHERE rowid=?",
                (result["proposed_name"], result["reason"], rec["rowid"])
            )
            # teach the preference engine this was auto-approved
            if engine:
                engine.learn(result, approved=True, note="auto_approve")
            counts["auto_approved"] += 1

        elif decision == "queue":
            c.execute(
                "UPDATE files SET proposed_name=?, approved=NULL, approval_note=? WHERE rowid=?",
                (result["proposed_name"], result["reason"], rec["rowid"])
            )
            counts["queued"] += 1

        else:
            counts["skipped"] += 1

    if not dry_run:
        con.commit()
        if engine:
            engine.save()

    con.close()
    return counts


def record_user_decision(db_path: str, file_rowid: int, approved: bool, note: str = ""):
    """
    Called when user manually approves or rejects a queued naming proposal.
    Updates the DB and immediately teaches the preference engine.
    """
    import sqlite3
    engine = _get_pref_engine() if PREF_ENGINE_OK else None

    con = sqlite3.connect(db_path)
    c   = con.cursor()
    row = c.execute(
        "SELECT proposed_name, chi_domain, content_type, chi_confidence FROM files WHERE rowid=?",
        (file_rowid,)
    ).fetchone()
    if row:
        proposal = {
            "proposed_name": row[0],
            "domain_code":   row[0].split("__")[0] if row[0] else "GN",
            "ct_code":       row[0].split("__")[1] if row[0] and "__" in row[0] else "DOC",
            "tags":          row[0].split("__")[2].split("-") if row[0] and row[0].count("__") >= 2 else [],
            "status_code":   row[0].split("__")[4].split(".")[0] if row[0] and row[0].count("__") >= 4 else "AC",
        }
        c.execute(
            "UPDATE files SET approved=?, approval_note=? WHERE rowid=?",
            (1 if approved else 0, note, file_rowid)
        )
        con.commit()
        if engine:
            engine.learn(proposal, approved=approved, note=note)
            engine.save()
    con.close()


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "fis_catalog.db"
    dry = "--dry" in sys.argv
    result = run_auto_approve(db, dry_run=dry)
    print(result)
