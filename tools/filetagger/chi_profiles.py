#!/usr/bin/env python3
"""
Chi Pipeline Profiles — swap the lens, same engine.
====================================================
Same structure: jurisdiction → classify → diagnose.
Different words for different domains.

Usage:
  python chi_profiles.py --list
  python chi_profiles.py --profile negotiation "contract.pdf"
  python chi_profiles.py --profile political "speech.html"
  python chi_profiles.py --profile therapy --text "You never listen to me"
  python chi_profiles.py --profile master_equation "paper.md" --all
  python chi_profiles.py --profile content_mod "post.txt" --law5

Profiles are just term dictionaries. Add new ones by adding to PROFILES dict.
"""
import argparse, json, re, html as html_mod, sys, time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

STOP = set("the a an and or of to in is it for on with as by at from this that be are "
    "was were will would can could should not no but if then else your our their his "
    "her its my me us them which who what when where how why all any some more most "
    "other into over under out up down off than too very just have has had do does did "
    "been being about also such only there here".split())

HTML_STRIP = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
HTML_TAGS = re.compile(r"(?s)<[^>]+>")

# ═══════════════════════════════════════════════════════════
#  PROFILES — same structure, different lens
#  Each profile has: justice_terms, mercy_terms, cost_terms,
#  coercion_terms, evidence_terms, overclaim_terms,
#  positive_terms (fruit), negative_terms (anti-fruit),
#  and a description.
#  Add a new domain = add a new dict entry. That's it.
# ═══════════════════════════════════════════════════════════

PROFILES = {

"master_equation": {
    "name": "Theophysics / Master Equation",
    "description": "Full framework lens — theology, physics, moral structure",
    "justice": ["accountability","consequence","judgment","restitution","boundary",
        "violation","debt","responsibility","penalty","standard","truth"],
    "mercy": ["grace","mercy","forgiveness","patience","restoration","reconciliation",
        "repair","compassion","dignity","healing","redemption","second chance"],
    "cost_bearer": ["pay","cost","absorb","bear","carry","sacrifice","restitution",
        "atone","repair","compensate","substitute","mediator","cross","price"],
    "coercion": ["force","coerce","dominate","manipulate","scapegoat","blame",
        "externalize","displace","demand","compel","control"],
    "evidence": ["source","citation","data","study","measurement","observed",
        "peer-reviewed","replication","statistical","sample","empirical"],
    "overclaim": ["proves","undeniable","impossible","always","never",
        "no one can deny","without exception","absolute","definitively"],
    "positive": ["love","joy","peace","patience","kindness","goodness",
        "faithfulness","gentleness","self-control","hope","humility"],
    "negative": ["hatred","despair","anxiety","cruelty","corruption",
        "betrayal","harshness","addiction","rage","domination","contempt"],
},

"negotiation": {
    "name": "Negotiation / Contract Analysis",
    "description": "Who pays, who benefits, is the deal fair?",
    "justice": ["liability","obligation","breach","penalty","warranty","indemnify",
        "guarantee","binding","enforceable","damages","termination","default"],
    "mercy": ["waiver","concession","flexibility","extension","accommodation",
        "renegotiate","forgive","adjust","compromise","goodwill","grace period"],
    "cost_bearer": ["pay","reimburse","compensate","indemnify","absorb","fund",
        "at expense of","cost borne by","responsible party","fee","charge"],
    "coercion": ["non-negotiable","take it or leave","mandatory","unilateral",
        "sole discretion","irrevocable","forfeit","penalty clause","liquidated damages"],
    "evidence": ["whereas","exhibit","schedule","appendix","reference","pursuant",
        "documented","recorded","agreed upon","specified","defined herein"],
    "overclaim": ["absolute","perpetual","irrevocable","unlimited","unconditional",
        "sole and exclusive","without limitation","in all circumstances"],
    "positive": ["mutual benefit","partnership","collaboration","fair","equitable",
        "reasonable","balanced","transparent","good faith"],
    "negative": ["predatory","unconscionable","exploitative","deceptive",
        "misleading","one-sided","oppressive","coercive","fraudulent"],
},

"political": {
    "name": "Political Analysis",
    "description": "Policy coherence — who benefits, who pays, who's scapegoated?",
    "justice": ["accountability","enforce","law","regulation","consequence","penalty",
        "prosecution","sanction","mandate","compliance","oversight","audit"],
    "mercy": ["amnesty","pardon","clemency","second chance","rehabilitation",
        "restorative","reintegration","compassionate","humanitarian","relief"],
    "cost_bearer": ["taxpayer","funded by","budget","deficit","cost to","burden on",
        "who pays","at whose expense","subsidy","transfer","redistribution"],
    "coercion": ["mandate","compel","force","require","criminalize","ban","censor",
        "surveillance","detain","deport","confiscate","override","executive order"],
    "evidence": ["data shows","study found","statistics","census","report",
        "according to","research","peer-reviewed","analysis","survey"],
    "overclaim": ["always","never","every","all Americans","no one","crisis",
        "existential","unprecedented","emergency","once and for all"],
    "positive": ["freedom","liberty","dignity","rights","equality","opportunity",
        "prosperity","security","unity","cooperation","bipartisan"],
    "negative": ["tyranny","oppression","corruption","propaganda","extremism",
        "radicalization","division","polarization","disinformation","authoritarian"],
},

"therapy": {
    "name": "Therapy / Conflict Resolution",
    "description": "Relational coherence — who's heard, who's accountable, is repair real?",
    "justice": ["accountability","responsibility","acknowledge","admit","own it",
        "boundary","consequence","honest","truth","confront","address","name it"],
    "mercy": ["forgive","patience","empathy","compassion","understanding","grace",
        "safe space","hear you","validate","accept","unconditional","gentle"],
    "cost_bearer": ["willing to","I will","take responsibility","my part","I own",
        "work on myself","show up","commitment","invest","effort","sacrifice"],
    "coercion": ["gaslight","manipulate","guilt trip","silent treatment","threaten",
        "control","dismiss","invalidate","stonewalling","blame shift","weaponize"],
    "evidence": ["specific","example","when you said","I noticed","pattern",
        "behavior","incident","repeated","consistent","observed"],
    "overclaim": ["always","never","every time","you never","you always",
        "everyone knows","nobody","nothing ever","impossible","hopeless"],
    "positive": ["love","trust","safety","connection","repair","growth","healing",
        "vulnerability","intimacy","respect","support","encourage"],
    "negative": ["contempt","criticism","defensiveness","stonewalling","resentment",
        "betrayal","abandonment","neglect","hostility","withdrawal","shame"],
},

"content_mod": {
    "name": "Content Moderation",
    "description": "Structural manipulation detection — beyond keyword toxicity",
    "justice": ["accountability","report","violation","policy","standards",
        "consequence","enforcement","review","flagged","terms of service"],
    "mercy": ["appeal","second chance","reinstate","context","nuance",
        "misunderstanding","good faith","benefit of doubt","restore"],
    "cost_bearer": ["who is harmed","victim","target","affected party",
        "at risk","vulnerable","community impact","collateral"],
    "coercion": ["brigade","harass","dogpile","mob","cancel","doxx","silence",
        "deplatform","censor","bully","intimidate","threaten","target"],
    "evidence": ["screenshot","archive","link","source","original post",
        "context","full quote","verified","confirmed","documented"],
    "overclaim": ["always","never","everyone","nobody","literally",
        "objectively","undeniable","obviously","clearly","unquestionable"],
    "positive": ["constructive","dialogue","good faith","nuance","context",
        "understanding","civil","respectful","bridge","listen"],
    "negative": ["toxic","hateful","abusive","threatening","dehumanizing",
        "extremist","radicalize","propaganda","disinformation","incitement"],
},

"corporate": {
    "name": "Corporate / PR Apology Analysis",
    "description": "Is this apology real or performed?",
    "justice": ["accountability","responsibility","investigation","findings",
        "root cause","corrective action","policy change","fired","disciplined"],
    "mercy": ["sorry","apologize","regret","understand","empathize",
        "committed to","moving forward","learning","improved"],
    "cost_bearer": ["we will pay","compensation","refund","restitution",
        "settlement","at our expense","funded","allocated","invested"],
    "coercion": ["thoughts and prayers","any inconvenience","mistakes were made",
        "bad actors","isolated incident","both sides","taken out of context"],
    "evidence": ["investigation","report","audit","review","findings",
        "independent","third party","timeline","facts"],
    "overclaim": ["industry leading","best in class","zero tolerance",
        "never again","world class","committed to excellence","fully"],
    "positive": ["transparent","accountable","genuine","concrete","specific",
        "measurable","timeline","follow up","check in"],
    "negative": ["vague","deflect","minimize","blame","passive voice",
        "weasel words","spin","rebrand","distract","pivot"],
},

"legal": {
    "name": "Legal / Restorative Justice",
    "description": "Does the legal resolution actually resolve?",
    "justice": ["guilty","liable","verdict","sentence","damages","judgment",
        "conviction","ruling","precedent","statute","violation","offense"],
    "mercy": ["clemency","parole","probation","rehabilitation","diversion",
        "restorative","mediation","plea bargain","reduced","mitigating"],
    "cost_bearer": ["defendant","plaintiff","state","victim compensation",
        "restitution","fine","community service","incarceration cost","taxpayer"],
    "coercion": ["mandatory minimum","three strikes","civil forfeiture",
        "qualified immunity","prosecutorial discretion","plea coercion",
        "overcriminalize","mass incarceration"],
    "evidence": ["exhibit","testimony","forensic","witness","deposition",
        "discovery","record","chain of custody","admissible","stipulated"],
    "overclaim": ["open and shut","slam dunk","clearly guilty","obviously",
        "without question","irrefutable","beyond any doubt"],
    "positive": ["due process","fair trial","equal protection","rights",
        "representation","presumption of innocence","proportional"],
    "negative": ["railroaded","kangaroo court","witch hunt","persecution",
        "entrapment","prejudice","bias","corruption","obstruction"],
},

}

# ═══════════════════════════════════════════════════════════
#  ENGINE — same for every profile
# ═══════════════════════════════════════════════════════════

def clean_text(text, ext=""):
    if ext in (".html", ".htm"):
        text = HTML_STRIP.sub(" ", text)
        text = re.sub(r"(?is)</(p|div|section|article|li|h[1-6]|tr)>", "\n", text)
        text = HTML_TAGS.sub(" ", text)
        text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def word_tokens(text):
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP]

def count_hits(text, terms):
    low = text.lower()
    hits = 0
    for t in terms:
        if " " in t:
            hits += low.count(t)
        elif re.search(rf"\b{re.escape(t)}\b", low):
            hits += 1
    return hits

def analyze(text: str, profile_name: str) -> dict:
    """Run one profile against text. Returns full diagnostic."""
    p = PROFILES[profile_name]
    low = text.lower()
    words = len(word_tokens(text))

    # Raw counts
    j = count_hits(text, p["justice"])
    m = count_hits(text, p["mercy"])
    c = count_hits(text, p["cost_bearer"])
    x = count_hits(text, p["coercion"])
    ev = count_hits(text, p["evidence"])
    oc = count_hits(text, p["overclaim"])
    pos = count_hits(text, p["positive"])
    neg = count_hits(text, p["negative"])

    # Scale to 0-100
    scale = lambda raw, k=12: min(100, raw * k)
    j_s, m_s, c_s, x_s = scale(j), scale(m), scale(c, 14), scale(x, 16)
    ev_s, oc_s = scale(ev), scale(oc, 18)
    pos_s, neg_s = scale(pos), scale(neg)

    # Coherence = min(justice, mercy) + cost_bearer - coercion
    coherence = max(0, min(100, min(j_s, m_s) + c_s - x_s))

    # Ratios (safe division)
    jm_ratio = round(j_s / max(1, m_s), 2)
    balance = j_s - m_s
    ev_oc_ratio = round(ev_s / max(1, oc_s), 2)

    # Diagnosis emerges from ratios, not hardcoded buckets
    signals = []
    if j_s > 50 and m_s < 15: signals.append("terminal justice -- mercy absent")
    if m_s > 50 and j_s < 15: signals.append("false mercy -- justice absent")
    if j_s > 30 and m_s > 30 and c_s < 10: signals.append("contradiction -- both demanded, no payer")
    if j_s > 30 and m_s > 30 and c_s > 25: signals.append("resolution path present")
    if x_s > 40: signals.append("coercion pressure detected")
    if c_s > 40 and m_s < 10: signals.append("cost language without restoration target")
    if oc_s > ev_s + 15: signals.append("overclaim exceeds evidence")
    if ev_s > oc_s + 20: signals.append("evidence-grounded")
    if neg_s > pos_s + 20: signals.append("negative signal dominant")
    if pos_s > neg_s + 20: signals.append("positive signal dominant")
    if j_s < 10 and m_s < 10: signals.append("low moral signal overall")
    if not signals: signals.append("neutral -- insufficient signal to diagnose")

    return {
        "profile": profile_name,
        "profile_name": p["name"],
        "word_count": words,
        "raw": {"justice": j, "mercy": m, "cost_bearer": c, "coercion": x,
                "evidence": ev, "overclaim": oc, "positive": pos, "negative": neg},
        "scores": {"justice": j_s, "mercy": m_s, "cost_bearer": c_s, "coercion": x_s,
                   "evidence": ev_s, "overclaim": oc_s, "positive": pos_s, "negative": neg_s},
        "coherence": coherence,
        "ratios": {"justice_mercy": jm_ratio, "balance": balance, "evidence_overclaim": ev_oc_ratio},
        "diagnosis": signals,
    }

def print_report(result: dict, path: str = ""):
    p = result
    print(f"\n{'='*60}")
    print(f"  {p['profile_name'].upper()}")
    if path: print(f"  {path}")
    print(f"  Words: {p['word_count']}")
    print(f"{'='*60}")
    s = p["scores"]
    print(f"\n  Justice:      {s['justice']:3d}   {'|' * (s['justice']//5)}")
    print(f"  Mercy:        {s['mercy']:3d}   {'|' * (s['mercy']//5)}")
    print(f"  Cost-bearer:  {s['cost_bearer']:3d}   {'|' * (s['cost_bearer']//5)}")
    print(f"  Coercion:     {s['coercion']:3d}   {'|' * (s['coercion']//5)}")
    print(f"  Evidence:     {s['evidence']:3d}   {'|' * (s['evidence']//5)}")
    print(f"  Overclaim:    {s['overclaim']:3d}   {'|' * (s['overclaim']//5)}")
    print(f"  Positive:     {s['positive']:3d}   {'|' * (s['positive']//5)}")
    print(f"  Negative:     {s['negative']:3d}   {'|' * (s['negative']//5)}")
    r = p["ratios"]
    print(f"\n  Coherence:        {p['coherence']}")
    print(f"  Justice/Mercy:    {r['justice_mercy']}x")
    print(f"  J-M Balance:      {r['balance']:+d}")
    print(f"  Evidence/Overcl:  {r['evidence_overclaim']}x")
    print(f"\n  DIAGNOSIS:")
    for d in p["diagnosis"]:
        print(f"    - {d}")
    print(f"{'='*60}\n")

# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Chi Profiles — same engine, different lens")
    ap.add_argument("path", nargs="?", help="File to analyze")
    ap.add_argument("--profile", "-p", default="master_equation",
                    help="Profile name (or 'all' to run every profile)")
    ap.add_argument("--list", action="store_true", help="List available profiles")
    ap.add_argument("--text", "-t", help="Analyze raw text instead of file")
    ap.add_argument("--output", "-o", help="Write JSON report")
    ap.add_argument("--compare", action="store_true",
                    help="Run ALL profiles and compare results")
    a = ap.parse_args()

    if a.list:
        print(f"\n  Available profiles ({len(PROFILES)}):\n")
        for key, p in PROFILES.items():
            print(f"    {key:20s}  {p['description']}")
        print()
        return 0

    # Get text
    if a.text:
        text = a.text
        label = "cli-input"
        ext = ""
    elif a.path:
        p = Path(a.path)
        if not p.exists():
            print(f"Not found: {a.path}"); return 1
        ext = p.suffix.lower()
        text = p.read_text(encoding="utf-8", errors="replace")
        text = clean_text(text, ext)
        label = str(p)
    else:
        ap.error("Provide --text or a file path")

    # Run
    if a.compare or a.profile == "all":
        results = {}
        for profile_name in PROFILES:
            result = analyze(text, profile_name)
            results[profile_name] = result
            print_report(result, label)
        # Comparison summary
        print(f"{'='*60}")
        print(f"  CROSS-PROFILE COMPARISON")
        print(f"{'='*60}")
        print(f"  {'Profile':<20s} {'Coher':>6s} {'J':>4s} {'M':>4s} {'C$':>4s} {'Coer':>4s}")
        print(f"  {'-'*42}")
        for name, r in results.items():
            s = r["scores"]
            print(f"  {name:<20s} {r['coherence']:5d} {s['justice']:4d} {s['mercy']:4d} {s['cost_bearer']:4d} {s['coercion']:4d}")
        print(f"{'='*60}\n")
        if a.output:
            Path(a.output).write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        result = analyze(text, a.profile)
        print_report(result, label)
        if a.output:
            Path(a.output).write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
