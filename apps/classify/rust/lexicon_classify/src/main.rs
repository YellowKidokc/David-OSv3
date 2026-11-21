//! Pass 1 lexicon classifier for David-OS / FIS.
//!
//! Reads files (never writes, moves or renames them), scans text against
//! LEXICON_LOOKUP.json and emits one JSON line per file with the 10-axis
//! classification defined in classification_2_0.json. No network access.
//!
//! Usage:
//!   lexicon_classify --lexicon LEXICON_LOOKUP.json [--taxonomy classification_2_0.json]
//!                    [--out FILE.jsonl] [--cache FILE.jsonl] [--ignore-frontmatter]
//!                    [--max-bytes N] PATH...
use rayon::prelude::*;
use regex::Regex;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use walkdir::WalkDir;

const PRODUCER: &str = "classify/lexicon@0.1.0";
const CHI: [&str; 10] = ["G", "M", "E", "S", "T", "K", "R", "Q", "F", "C"];
const ROLE_SIGNALS: [&str; 5] = ["claim", "evidence", "bridge", "falsifier", "dependency"];
const MAX_NGRAM: usize = 7;
const TERM_CAP: usize = 3; // a term scores at most this many times per file
const TITLE_BOOST: f64 = 3.0; // weight of terms in the file name or first heading

// ------------------------------------------------------------------ lexicon
#[derive(Default, Clone)]
struct Entry {
    chi: Vec<String>,
    doc_type: Vec<String>,
    signal: Vec<String>,
    domain: Vec<String>,
    bucket: Vec<String>,
    subbucket: Vec<String>,
    weight: f64,
}

struct Lexicon {
    phrases: HashMap<String, Entry>,
    patterns: Vec<(String, Regex, Entry)>,
    skipped: Vec<String>,
    hash: String,
}

fn strs(v: Option<&Value>) -> Vec<String> {
    match v {
        Some(Value::String(s)) => vec![s.clone()],
        Some(Value::Array(a)) => a.iter().filter_map(|x| x.as_str().map(String::from)).collect(),
        _ => vec![],
    }
}

fn weight_of(v: Option<&Value>) -> f64 {
    match v {
        Some(Value::Number(n)) => n.as_f64().unwrap_or(1.0),
        Some(Value::Array(a)) => a.iter().filter_map(|x| x.as_f64()).fold(1.0, f64::max),
        _ => 1.0,
    }
}

fn is_word_char(c: char) -> bool {
    c.is_alphanumeric() || c == '\'' || c == '-' || c == '\u{2019}'
}

/// Lowercase word tokens; hyphens and apostrophes stay inside words.
fn words(text: &str) -> Vec<String> {
    text.to_lowercase()
        .split(|c: char| !is_word_char(c))
        .map(|w| {
            w.trim_matches(|c: char| c == '-' || c == '\'' || c == '\u{2019}')
                .replace('\u{2019}', "'")
        })
        .filter(|w| !w.is_empty())
        .collect()
}

fn load_lexicon(path: &Path) -> Lexicon {
    let raw = fs::read(path).unwrap_or_else(|e| panic!("cannot read lexicon {}: {e}", path.display()));
    let hash = hex(&Sha256::digest(&raw))[..16].to_string();
    let map: Map<String, Value> = serde_json::from_slice(&raw).expect("lexicon is not a JSON object");
    let (mut phrases, mut patterns, mut skipped) = (HashMap::new(), vec![], vec![]);
    for (term, axes) in map {
        let e = Entry {
            chi: strs(axes.get("chi_primary")).into_iter().chain(strs(axes.get("chi_hint"))).collect(),
            doc_type: strs(axes.get("document_type")),
            signal: strs(axes.get("epistemic_signal")),
            domain: strs(axes.get("subject_domain")),
            bucket: strs(axes.get("semantic_bucket")),
            subbucket: strs(axes.get("subbucket")),
            weight: weight_of(axes.get("weight")),
        };
        // sheet names / file paths that leaked into the workbook export
        let junk = term.contains(":\\")
            || ["_lexicon", "_terms", "_patterns"].iter().any(|s| term.ends_with(s))
            || term == "fruits";
        if junk {
            skipped.push(term);
        } else if term.contains('\\') {
            match Regex::new(&format!("(?i){term}")) {
                Ok(rx) => patterns.push((term, rx, e)),
                Err(_) => skipped.push(term),
            }
        } else {
            let key = words(&term).join(" ");
            if key.is_empty() {
                skipped.push(term);
            } else {
                phrases.insert(key, e);
            }
        }
    }
    skipped.sort();
    Lexicon { phrases, patterns, skipped, hash }
}

// ------------------------------------------------------------------ helpers
fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn ext_of(p: &Path) -> String {
    p.extension()
        .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
        .unwrap_or_default()
}

/// Pass 0 extension rules -> (document_type, physical_home, read_text)
fn ext_rule(ext: &str) -> Option<(&'static str, &'static str, bool)> {
    Some(match ext {
        ".py" | ".ps1" | ".bat" | ".js" | ".ts" | ".rs" | ".sh" | ".css" => ("code", "80_SYSTEM", false),
        ".json" | ".jsonl" | ".csv" | ".yaml" | ".yml" | ".xlsx" | ".db" | ".sqlite" => {
            ("dataset", "60_MEDIA_DATA", false)
        }
        ".mp3" | ".wav" | ".mp4" | ".mov" | ".png" | ".jpg" | ".jpeg" | ".svg" | ".gif" | ".webp" => {
            ("media", "60_MEDIA_DATA", false)
        }
        ".pdf" | ".epub" => ("source", "30_SOURCES", false), // no PDF text extraction yet
        ".lean" => ("lean_file", "40_CANONIZATION", false),
        ".md" | ".txt" | ".html" | ".htm" | ".tex" | ".rst" => ("", "", true),
        _ => return None,
    })
}

fn name_rule(name: &str) -> Option<&'static str> {
    static RULES: OnceLock<Vec<(Regex, &'static str)>> = OnceLock::new();
    let rules = RULES.get_or_init(|| {
        vec![
            (Regex::new(r"receipt|_log|sort_log|migration|changelog").unwrap(), "receipt"),
            (Regex::new(r"^prompt|_prompt|session|chat_export").unwrap(), "prompt"),
            (Regex::new(r"template").unwrap(), "template"),
            (Regex::new(r"^untitled|kanban").unwrap(), "draft"),
        ]
    });
    let n = name.to_lowercase();
    rules.iter().find(|(rx, _)| rx.is_match(&n)).map(|(_, t)| *t)
}

fn unquote(s: &str) -> &str {
    s.trim().trim_matches('"').trim_matches('\'')
}

/// Minimal YAML frontmatter reader: top-level `key: value` and `key: [a, b]`.
fn frontmatter(text: &str) -> (BTreeMap<String, Value>, String) {
    let mut out = BTreeMap::new();
    let t = text.trim_start_matches('\u{feff}').replace("\r\n", "\n");
    if !t.starts_with("---\n") {
        return (out, t);
    }
    let rest = &t[4..];
    let Some(end) = rest.find("\n---") else { return (out, t.clone()) };
    for line in rest[..end].lines() {
        if line.starts_with(' ') || line.starts_with('\t') {
            continue;
        }
        let Some((k, v)) = line.split_once(':') else { continue };
        let v = v.trim();
        let val = if v.starts_with('[') && v.ends_with(']') {
            Value::Array(
                v[1..v.len() - 1]
                    .split(',')
                    .map(unquote)
                    .filter(|s| !s.is_empty())
                    .map(|s| Value::String(s.into()))
                    .collect(),
            )
        } else {
            Value::String(unquote(v).into())
        };
        out.insert(k.trim().to_string(), val);
    }
    let body = rest[end + 4..].to_string();
    (out, body)
}

fn strip_html(s: &str) -> String {
    static RX: OnceLock<(Regex, Regex)> = OnceLock::new();
    let (a, b) = RX.get_or_init(|| {
        (
            Regex::new(r"(?is)<script\b.*?</script>|<style\b.*?</style>").unwrap(),
            Regex::new(r"<[^>]+>").unwrap(),
        )
    });
    b.replace_all(&a.replace_all(s, " "), " ").into_owned()
}

fn top(m: &HashMap<String, f64>) -> Option<(String, f64)> {
    m.iter()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap().then_with(|| b.0.cmp(a.0)))
        .map(|(k, v)| (k.clone(), *v))
}

fn fm_str(fm: &BTreeMap<String, Value>, k: &str) -> Option<String> {
    fm.get(k).and_then(|v| v.as_str()).filter(|s| !s.is_empty()).map(String::from)
}

fn round3(x: f64) -> f64 {
    (x * 1000.0).round() / 1000.0
}

// ------------------------------------------------------------------ classify
struct Opts {
    ignore_fm: bool,
    max_bytes: usize,
}

#[derive(Default)]
struct Scores {
    chi: HashMap<String, f64>,
    doc: HashMap<String, f64>,
    sig: HashMap<String, f64>,
    dom: HashMap<String, f64>,
    bucket: HashMap<String, f64>,
    matched: BTreeMap<String, usize>,
}

impl Scores {
    /// Score one occurrence. `boost` > 1 for title/filename hits. Each term
    /// scores at most TERM_CAP times so one repeated word can't decide a file.
    fn hit(&mut self, e: &Entry, term: &str, boost: f64) {
        let seen = self.matched.entry(term.to_string()).or_default();
        *seen += 1;
        if *seen > TERM_CAP && boost <= 1.0 {
            return;
        }
        let n = e.chi.len().max(1) as f64;
        for c in &e.chi {
            *self.chi.entry(c.clone()).or_default() += boost / n;
        }
        for t in &e.doc_type {
            *self.doc.entry(t.clone()).or_default() += boost;
        }
        for s in &e.signal {
            *self.sig.entry(s.clone()).or_default() += 1.0;
        }
        for d in &e.domain {
            *self.dom.entry(d.clone()).or_default() += boost;
        }
        for (i, b) in e.bucket.iter().enumerate() {
            *self.bucket.entry(b.clone()).or_default() += e.weight;
            if let Some(sb) = e.subbucket.get(i).or(e.subbucket.first()) {
                *self.bucket.entry(format!("{b}/{sb}")).or_default() += e.weight;
            }
        }
    }
}

fn scan_words(ws: &[String], lx: &Lexicon, s: &mut Scores, boost: f64) {
    let mut buf = String::with_capacity(96);
    for i in 0..ws.len() {
        buf.clear();
        for n in 0..MAX_NGRAM.min(ws.len() - i) {
            if n > 0 {
                buf.push(' ');
            }
            buf.push_str(&ws[i + n]);
            if let Some(e) = lx.phrases.get(buf.as_str()) {
                let term = buf.clone();
                s.hit(e, &term, boost);
            }
        }
    }
}

/// Title = file stem + first markdown heading; its terms count TITLE_BOOST times.
fn scan(title: &str, body: &str, lx: &Lexicon) -> (Scores, usize) {
    let mut s = Scores::default();
    scan_words(&words(title), lx, &mut s, TITLE_BOOST);
    let ws = words(body);
    scan_words(&ws, lx, &mut s, 1.0);
    for (term, rx, e) in &lx.patterns {
        for _ in rx.find_iter(body).take(50) {
            s.hit(e, term, 1.0);
        }
    }
    (s, ws.len())
}

fn title_of(stem: &str, body: &str) -> String {
    let heading = body
        .lines()
        .find(|l| l.trim_start().starts_with('#'))
        .map(|l| l.trim_start_matches(|c: char| c == '#' || c.is_whitespace()))
        .unwrap_or("");
    format!("{} {}", stem.replace(['_', '-'], " "), heading)
}

fn classify(path: &Path, bytes: &[u8], sha: &str, lx: &Lexicon, o: &Opts, now: &str) -> Value {
    let ext = ext_of(path);
    let name = path.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
    let path_s = path.to_string_lossy().replace('\\', "/");
    let mut flags: Vec<String> = vec![];
    let mut reasons: Vec<String> = vec![];

    // ---- Pass 0: extension + filename rules
    let rule = ext_rule(&ext);
    let mut doc_type: Option<String> = rule.map(|r| r.0.to_string()).filter(|s| !s.is_empty());
    let rule_home: Option<String> = rule.map(|r| r.1.to_string()).filter(|s| !s.is_empty());
    let read_text = rule.map(|r| r.2).unwrap_or(false);
    if let Some(t) = &doc_type {
        reasons.push(format!("extension {ext} -> {t}"));
    }
    if rule.is_none() {
        flags.push(format!("unhandled_extension:{}", if ext.is_empty() { "(none)" } else { &ext }));
    }
    if read_text {
        if let Some(t) = name_rule(&name) {
            doc_type = Some(t.into());
            reasons.push(format!("filename -> {t}"));
        }
    }

    // ---- Pass 1: lexicon scan
    let mut fm = BTreeMap::new();
    let (mut sc, mut n_words) = (Scores::default(), 0);
    if read_text {
        let raw = String::from_utf8_lossy(&bytes[..bytes.len().min(o.max_bytes)]).into_owned();
        let (f, body) = frontmatter(&raw);
        fm = f;
        let body = if ext == ".html" || ext == ".htm" { strip_html(&body) } else { body };
        let stem = path.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
        (sc, n_words) = scan(&title_of(&stem, &body), &body, lx);
    }

    // chi: winner-take-all over CHI variables
    let chi_total: f64 = sc.chi.iter().filter(|(k, _)| CHI.contains(&k.as_str())).map(|(_, v)| v).sum();
    let mut chi_rank: Vec<(String, f64)> = sc
        .chi
        .iter()
        .filter(|(k, _)| CHI.contains(&k.as_str()))
        .map(|(k, v)| (k.clone(), *v))
        .collect();
    chi_rank.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then_with(|| a.0.cmp(&b.0)));
    let (mut chi_primary, mut chi_conf) = match chi_rank.first() {
        Some((k, v)) if chi_total >= 2.0 => (k.clone(), (v / chi_total) * (chi_total / 8.0).min(1.0)),
        _ => ("none".to_string(), 0.0),
    };
    let chi_secondary: Vec<String> = if chi_primary == "none" {
        vec![]
    } else {
        chi_rank
            .iter()
            .skip(1)
            .filter(|(_, v)| *v >= 0.5 * chi_rank[0].1)
            .take(3)
            .map(|(k, _)| k.clone())
            .collect()
    };
    if chi_primary != "none" {
        reasons.push(format!("chi {chi_primary}: {:.1} of {:.1} hits", chi_rank[0].1, chi_total));
    }

    // epistemic roles and domains: thresholded, non-exclusive
    let sig = |k: &str| sc.sig.get(k).copied().unwrap_or(0.0);
    let mut roles: Vec<String> =
        ROLE_SIGNALS.iter().filter(|r| sig(r) >= 2.0).map(|r| r.to_string()).collect();
    roles.sort_by(|a, b| sig(b).partial_cmp(&sig(a)).unwrap().then_with(|| a.cmp(b)));
    let role_score: f64 = ROLE_SIGNALS.iter().map(|r| sig(r)).sum();
    let mut domains: Vec<String> = sc.dom.iter().filter(|(_, v)| **v >= 2.0).map(|(k, _)| k.clone()).collect();
    domains.sort();
    for (b, label) in [
        ("DANGER_LANGUAGE", "danger_language"),
        ("CLAIM_STRENGTH/forbidden_unless_formal", "forbidden_unless_formal"),
        ("DRIFT_WARNING", "drift_warning"),
        ("REVIEWER_RISK", "reviewer_risk"),
    ] {
        if sc.bucket.get(b).copied().unwrap_or(0.0) > 0.0 {
            flags.push(label.into());
        }
    }

    if doc_type.is_none() && read_text {
        match top(&sc.doc) {
            Some((t, v)) if v >= 2.0 => {
                reasons.push(format!("doc-type terms -> {t} ({v})"));
                doc_type = Some(t);
            }
            _ => doc_type = Some("note".into()),
        }
    }

    // lifecycle / canon / effort / series from path and name
    let lname = name.to_lowercase();
    let mut lifecycle = if lname.contains("draft") || lname.starts_with("untitled") {
        "draft"
    } else if path_s.contains("/90_ARCHIVE") || lname.contains("superseded") {
        "archived"
    } else {
        "working"
    }
    .to_string();
    let mut canon_status = "not_evaluated".to_string();
    let effort = path_s
        .split("10_ACTIVE_EFFORTS/")
        .nth(1)
        .and_then(|r| r.split('/').next())
        .filter(|s| !s.contains('.'))
        .unwrap_or("")
        .to_string();
    let mut series = String::new();

    // ---- frontmatter override (David's stamps win)
    let mut from_fm = false;
    if !o.ignore_fm && !fm.is_empty() {
        if let Some(v) = fm_str(&fm, "type").or(fm_str(&fm, "document_type")) {
            doc_type = Some(v);
            from_fm = true;
        }
        if let Some(v) = fm_str(&fm, "chi_primary") {
            chi_primary = v;
            chi_conf = 1.0;
            from_fm = true;
        }
        if let Some(v) = fm_str(&fm, "status").or(fm_str(&fm, "lifecycle")) {
            lifecycle = v;
        }
        if let Some(v) = fm_str(&fm, "canon_status") {
            canon_status = v;
        }
        if let Some(v) = fm_str(&fm, "series") {
            series = v;
        }
        if let Some(v) = fm_str(&fm, "canon_role") {
            if !roles.contains(&v) {
                roles.insert(0, v);
            }
        }
        if let Some(v) = fm_str(&fm, "domain") {
            if !domains.contains(&v) {
                domains.push(v);
            }
        }
        if from_fm {
            reasons.push("frontmatter override".into());
            flags.push("from_frontmatter".into());
        }
    }
    // R3: only a recorded ruling (frontmatter) may carry "admitted"
    if canon_status == "admitted" && !from_fm {
        canon_status = "candidate".into();
    }

    // ---- physical home + confidence
    let doc_type = doc_type.unwrap_or_else(|| "unknown".into());
    let has_chi = chi_primary != "none";
    let (mut home, mut confidence) = if let Some(h) = rule_home {
        let c = if doc_type == "source" { 0.6 } else { 0.9 };
        (h, c)
    } else if !read_text {
        ("99_REVIEW".to_string(), 0.3)
    } else {
        let lex = (chi_conf * 0.6 + (role_score / 10.0).min(1.0) * 0.4).min(0.97);
        let mut c = if from_fm { 0.95 } else { lex };
        let h = match doc_type.as_str() {
            "code" | "config" | "prompt" | "template" | "receipt" => {
                c = c.max(0.8);
                "80_SYSTEM"
            }
            "dataset" | "media" => "60_MEDIA_DATA",
            "source" | "transcript" => "30_SOURCES",
            "article" | "story" | "series_paper" if lifecycle == "final" || lifecycle == "published" => {
                "50_PRODUCTION"
            }
            _ if has_chi && role_score >= 4.0 => "40_CANONIZATION",
            _ if has_chi => "20_KNOWLEDGE_ATLAS",
            _ => "99_REVIEW",
        };
        (h.to_string(), c)
    };
    if confidence < 0.5 {
        if home != "99_REVIEW" {
            flags.push(format!("low_confidence_home:{home}"));
        }
        home = "99_REVIEW".into();
        flags.push("pass2_needed".into());
    }
    confidence = round3(confidence);
    let sub = match home.as_str() {
        "40_CANONIZATION" => "40_CANONIZATION/01_CANDIDATE".to_string(),
        h => h.to_string(),
    };
    let status = if flags.iter().any(|f| f == "pass2_needed") { "needs_review" } else { "ok" };
    let mut top_terms: Vec<(&String, &usize)> = sc.matched.iter().collect();
    top_terms.sort_by(|a, b| b.1.cmp(a.1).then_with(|| a.0.cmp(b.0)));

    json!({
        "schema_version": "classification.v1",
        "producer": PRODUCER,
        "created_at": now,
        "source_path": path.to_string_lossy(),
        "sha256": sha,
        "status": status,
        "classifier": "lexicon",
        "labels": [
            {"label": format!("physical_home:{home}"), "confidence": confidence},
            {"label": format!("document_type:{doc_type}"), "confidence": confidence},
            {"label": format!("chi:{chi_primary}"), "confidence": round3(chi_conf)},
        ],
        "file": path.to_string_lossy(),
        "physical_home": home,
        "physical_subfolder": sub,
        "document_type": doc_type,
        "epistemic_roles": if roles.is_empty() { vec!["none".to_string()] } else { roles },
        "subject_domains": if domains.is_empty() { vec!["other".to_string()] } else { domains },
        "lifecycle": lifecycle,
        "canon_status": canon_status,
        "series": series,
        "effort": effort,
        "chi_primary": chi_primary,
        "chi_secondary": chi_secondary,
        "confidence": confidence,
        "reason": reasons.join("; "),
        "matched_terms": top_terms.iter().take(25).map(|(k, _)| (*k).clone()).collect::<Vec<_>>(),
        "evidence": top_terms.iter().take(10).map(|(k, n)| format!("{k} x{n}")).collect::<Vec<_>>(),
        "flags": flags,
        "tier": "lexicon",
        "lexicon_version": lx.hash,
        "words_scanned": n_words,
    })
}

// ------------------------------------------------------------------ main
fn main() {
    let mut args = std::env::args().skip(1);
    let (mut lexicon, mut taxonomy, mut out, mut cache) = (None, None, None, None);
    let mut opts = Opts { ignore_fm: false, max_bytes: 2_000_000 };
    let mut roots: Vec<PathBuf> = vec![];
    while let Some(a) = args.next() {
        match a.as_str() {
            "--lexicon" => lexicon = args.next().map(PathBuf::from),
            "--taxonomy" => taxonomy = args.next().map(PathBuf::from),
            "--out" => out = args.next().map(PathBuf::from),
            "--cache" => cache = args.next().map(PathBuf::from),
            "--ignore-frontmatter" => opts.ignore_fm = true,
            "--max-bytes" => {
                opts.max_bytes = args.next().and_then(|s| s.parse().ok()).unwrap_or(opts.max_bytes)
            }
            "-h" | "--help" => {
                eprintln!("usage: see the header of src/main.rs");
                return;
            }
            _ => roots.push(PathBuf::from(a)),
        }
    }
    let lx = load_lexicon(&lexicon.expect("--lexicon required"));
    let vocab: HashSet<String> = taxonomy
        .as_ref()
        .map(|t| {
            let v: Value = serde_json::from_slice(&fs::read(t).expect("read taxonomy")).expect("taxonomy json");
            ["physical_home", "document_type"]
                .iter()
                .flat_map(|ax| {
                    v["axes"][ax]["values"]
                        .as_object()
                        .map(|m| m.keys().cloned().collect::<Vec<_>>())
                        .unwrap_or_default()
                })
                .collect()
        })
        .unwrap_or_default();
    eprintln!(
        "lexicon {}: {} phrases, {} patterns, {} skipped {:?}",
        lx.hash,
        lx.phrases.len(),
        lx.patterns.len(),
        lx.skipped.len(),
        lx.skipped
    );

    let mut files: Vec<PathBuf> = vec![];
    for r in &roots {
        for e in WalkDir::new(r).into_iter().filter_map(Result::ok) {
            if e.file_type().is_file() {
                files.push(e.into_path());
            }
        }
    }
    files.sort();

    let ckey = |sha: &str| format!("{sha}:{}:{}", lx.hash, opts.ignore_fm);
    let mut cached: HashMap<String, Value> = HashMap::new();
    if let Some(c) = &cache {
        if let Ok(f) = fs::File::open(c) {
            for line in BufReader::new(f).lines().map_while(Result::ok) {
                if let Ok(v) = serde_json::from_str::<Value>(&line) {
                    if let Some(k) = v["cache_key"].as_str() {
                        cached.insert(k.to_string(), v);
                    }
                }
            }
        }
    }

    let now = chrono::Utc::now().format("%Y-%m-%dT%H:%M:%S+00:00").to_string();
    let t0 = std::time::Instant::now();
    let results: Vec<(Value, bool)> = files
        .par_iter()
        .map(|p| match fs::read(p) {
            Err(e) => (
                json!({"schema_version": "classification.v1", "producer": PRODUCER, "created_at": now,
                       "source_path": p.to_string_lossy(), "sha256": "0".repeat(64), "status": "error",
                       "classifier": "lexicon", "labels": [], "error": e.to_string(),
                       "physical_home": "99_REVIEW", "tier": "lexicon"}),
                false,
            ),
            Ok(b) => {
                let sha = hex(&Sha256::digest(&b));
                let k = ckey(&sha);
                if let Some(v) = cached.get(&k) {
                    let mut v = v.clone();
                    v["source_path"] = json!(p.to_string_lossy());
                    v["file"] = v["source_path"].clone();
                    return (v, true);
                }
                let mut v = classify(p, &b, &sha, &lx, &opts, &now);
                v["cache_key"] = json!(k);
                (v, false)
            }
        })
        .collect();
    let secs = t0.elapsed().as_secs_f64();

    let mut w: Box<dyn Write> = match &out {
        Some(p) => {
            if let Some(d) = p.parent() {
                let _ = fs::create_dir_all(d);
            }
            Box::new(std::io::BufWriter::new(fs::File::create(p).expect("create --out file")))
        }
        None => Box::new(std::io::BufWriter::new(std::io::stdout().lock())),
    };
    let (mut off_vocab, mut new_cache) = (0usize, vec![]);
    for (v, hit) in &results {
        if !vocab.is_empty() {
            for ax in ["physical_home", "document_type"] {
                if let Some(s) = v[ax].as_str() {
                    if !vocab.contains(s) {
                        off_vocab += 1;
                    }
                }
            }
        }
        writeln!(w, "{v}").unwrap();
        if !hit && v["cache_key"].is_string() {
            new_cache.push(v.to_string());
        }
    }
    w.flush().unwrap();
    if let Some(c) = &cache {
        if !new_cache.is_empty() {
            let mut f = fs::OpenOptions::new().create(true).append(true).open(c).expect("open cache");
            for l in new_cache {
                writeln!(f, "{l}").unwrap();
            }
        }
    }
    let hits = results.iter().filter(|r| r.1).count();
    eprintln!(
        "classified {} files in {:.3}s ({:.0} files/s), cache hits {}, off-taxonomy values {}",
        results.len(),
        secs,
        results.len() as f64 / secs.max(1e-9),
        hits,
        off_vocab
    );
}
