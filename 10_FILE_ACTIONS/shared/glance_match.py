"""Glance matcher: score every vault page against one standard page per series.
Read-only. Signals: skeleton (page shape), rare words, boilerplate lines.
Usage: python glance_match.py <vault_root> <standards.tsv> <out_dir>
"""
import sys, os, re, math, json, csv, difflib, collections
from pathlib import Path

ROOT, STD, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
SKIP = re.compile(r'(?i)[\\/](\.obsidian|\.git|\.trash|node_modules|\.smart-env)[\\/]')
WORD = re.compile(r"[a-z][a-z'\-]{3,}")
STOP = set("that this with from have they their there which would could about into than then them what when where were will your more been also such these those only other some most very just over even because being does".split())

def read(p):
    try:
        with open(p, encoding='utf-8', errors='replace') as fh: return fh.read(200000)
    except Exception: return ''

def strip_fm(t): return re.sub(r'(?s)\A---\n.*?\n---\n', '', t)

def skeleton(t):
    out = []
    for ln in strip_fm(t).splitlines():
        s = ln.strip()
        if not s: continue
        if s.startswith('#'): out.append('H%d' % (len(s) - len(s.lstrip('#'))))
        elif s.startswith('|'): out.append('T') if not out or out[-1] != 'T' else None
        elif re.match(r'^[-*+]\s|^\d+[.)]\s', s): out.append('L') if not out or out[-1] != 'L' else None
        elif s.startswith('>'): out.append('Q') if not out or out[-1] != 'Q' else None
        elif re.match(r'^\*\*[^*]{2,40}:?\*\*', s): out.append('B')
        elif s.startswith('```'): out.append('C')
        else: out.append('P') if not out or out[-1] != 'P' else None
    return out[:60]

def labels(t):
    return {re.sub(r'\W+', ' ', m.group(1)).strip().lower() for m in re.finditer(r'(?m)^\s*(?:#+\s*|\*\*)([^*\n]{3,50}?)(?:\*\*|:|\s*$)', strip_fm(t))}

def words(t): return [w for w in WORD.findall(strip_fm(t).lower()) if w not in STOP]

# ---- corpus pass: document frequency for rare-word weighting
TOPSKIP = re.compile(r'(?i)^(zzz|a3_archive|00_inbox|legacy_import|openai_data|nested_prod|theophysics_vault|codex_excel|03_media|30_bible|\.obsidian)')
files = []
for top in ROOT.iterdir():
    if top.is_dir() and not TOPSKIP.match(top.name):
        for dp, dn, fn in os.walk(top):
            dn[:] = [d for d in dn if not re.match(r'(?i)(zzz|archive|backup|legacy|\.obsidian|\.git|_upgrade|raw_source|full_copy)', d)]
            files += [Path(dp) / x for x in fn if x.endswith('.md')]
import hashlib
seen = set()
df = collections.Counter(); docs = {}
for i, p in enumerate(files):
    if i % 2000 == 0: print('read', i, '/', len(files), flush=True)
    t = read(p)
    if len(t) < 300: continue
    h = hashlib.md5(t.encode('utf-8', 'replace')).hexdigest()
    if h in seen: continue
    seen.add(h)
    w = words(t)
    docs[p] = (skeleton(t), labels(t), collections.Counter(w))
    df.update(set(w))
N = len(docs)
idf = lambda w: math.log((N + 1) / (df[w] + 1))

def fingerprint(cnt, k=25):
    sc = {w: c * idf(w) for w, c in cnt.items() if df[w] >= 2}
    return dict(sorted(sc.items(), key=lambda x: -x[1])[:k])

def wsim(fa, cb):
    tot = sum(fa.values()) or 1
    return sum(v for w, v in fa.items() if w in cb) / tot

stds = []
for line in STD.read_text(encoding='utf-8').splitlines():
    if '\t' not in line: continue
    s, rel = line.split('\t', 1)
    p = ROOT / rel
    if p in docs:
        sk, lb, cnt = docs[p]
        stds.append((s, p, sk, lb, fingerprint(cnt)))
    else:
        print('standard missing or too short:', s, rel)

rows = []
for j, (p, (sk, lb, cnt)) in enumerate(docs.items()):
    if j % 2000 == 0: print('score', j, '/', N, flush=True)
    best = None
    for s, sp, ssk, slb, sfp in stds:
        sm = difflib.SequenceMatcher(None, ssk, sk, autojunk=False)
        shape = sm.ratio() if sm.real_quick_ratio() > 0.3 else 0.0
        lab = len(slb & lb) / max(1, len(slb))
        rare = wsim(sfp, cnt)
        score = 0.40 * shape + 0.25 * lab + 0.35 * rare
        cand = (score, s, shape, lab, rare)
        if not best or cand > best: best = cand
    score, s, shape, lab, rare = best
    rows.append([s, round(score, 3), round(shape, 3), round(lab, 3), round(rare, 3), str(p.relative_to(ROOT))])

rows.sort(key=lambda r: (r[0], -r[1]))
with open(OUT / 'glance_matches.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['series', 'score', 'shape', 'labels', 'rare_words', 'path']); w.writerows(rows)

summary = {}
for s, *_ in stds:
    sc = [r for r in rows if r[0] == s]
    summary[s] = {'strong(>=.55)': sum(r[1] >= .55 for r in sc), 'likely(.40-.55)': sum(.40 <= r[1] < .55 for r in sc),
                  'top10': [(r[1], r[5]) for r in sorted(sc, key=lambda r: -r[1])[:10]]}
json.dump({'docs_scanned': N, 'series': summary}, open(OUT / 'glance_summary.json', 'w', encoding='utf-8'), indent=1)
print('scanned', N, 'docs')
for s, v in summary.items(): print(f"{s:6} strong {v['strong(>=.55)']:5}  likely {v['likely(.40-.55)']:5}")


