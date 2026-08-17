"""
tagger.py — topic slug + compressed tag codes (from fis_namer's tables).

Tags are short codes (CSN, COH, BKT, ...) so they never need spelling out in a
name. The slug is a short human-readable kebab topic pulled from the filename.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import config

# 2-4 letter topic codes. Keyword -> code. Order matters (first match wins).
TAG_ABBREVS: List[tuple] = [
    # Theophysics / theology
    (["consciousness", "aware", "sentien"], "CSN"),
    (["coherence", "coher"], "COH"),
    (["falsif", "refut", "disproof"], "FSL"),
    (["chi factor", "chi-factor", "χ"], "CHI"),
    (["grace", "agape", "shalom"], "GRC"),
    (["moral", "virtue", "fruit"], "MRL"),
    (["entropy", "disorder", "decay"], "ENT"),
    (["faith", "belief", "trust"], "FTH"),
    (["relation", "bond", "covenant"], "REL"),
    (["quantum", "superposit"], "QNT"),
    (["knowledge", "epistem", "truth"], "KNW"),
    (["time", "kairos", "temporal", "chronos"], "TMP"),
    (["logos", "scripture", "gospel"], "LGS"),
    (["law10", "l10", "omega", "telos"], "L10"),
    (["law04", "l04", "love", "strong force"], "L04"),
    # Day trading / finance
    (["premarket", "pre-market"], "PMK"),
    (["backtest", "back-test"], "BKT"),
    (["watchlist", "watch list"], "WTL"),
    (["risk", "stop loss", "drawdown"], "RSK"),
    (["strategy", "strat", "setup"], "STG"),
    (["signal", "indicator", "alert"], "SIG"),
    (["profit", "pnl", "return"], "PNL"),
    (["options", "calls", "puts", "expiry"], "OPT"),
    (["scanner", "screener"], "SCN"),
    (["journal", "trade log"], "JRN"),
    (["chart", "candlestick", "ohlc"], "CHT"),
    # Code / dev
    (["daemon", "background", "service", "worker"], "DMN"),
    (["server", "fastapi", "flask", "api"], "SRV"),
    (["classifier", "classify"], "CLF"),
    (["database", "sqlite", "schema"], "DBS"),
    (["config", "setting", "yaml"], "CFG"),
    (["autohotkey", "ahk"], "AHK"),
    (["html", "css", "frontend", "web"], "WEB"),
    (["installer", "install", "setup"], "INS"),
    (["watcher", "watchdog", "observer", "event"], "WCH"),
    # Evidence / research
    (["statistical", "sigma"], "STA"),
    (["audit", "verify"], "AUD"),
    (["claim", "assertion", "proposition"], "CLM"),
    (["axiom", "foundational"], "AXM"),
    (["corpus", "dataset", "training"], "CRP"),
    (["graph", "knowledge graph"], "GRP"),
    (["proof", "qed", "theorem", "lemma"], "PRF"),
    # Media
    (["screenshot", "screen shot"], "SCR"),
    (["thumbnail", "thumb", "preview"], "THM"),
    (["recording", "recorded"], "REC"),
    (["export", "render"], "EXP"),
]

_STRIP = re.compile(r"[_\-\s]+")
_JUNK = re.compile(
    r"\b(v\d+|final|copy|old|new|temp|tmp|test|draft|bak|backup|untitled"
    r"|document|file|data|the|and|for|with|from|this|that)\b", re.I,
)


def extract_tags(name: str, text: str = "", max_tags: int = None) -> List[str]:
    max_tags = max_tags or int(config.NAMING.get("max_tags", 3))
    blob = (name + " " + (text or ""))[:50_000].lower()
    seen, tags = set(), []
    for keywords, code in TAG_ABBREVS:
        if code in seen:
            continue
        if any(k in blob for k in keywords):
            seen.add(code)
            tags.append(code)
            if len(tags) >= max_tags:
                break
    return tags


def topic_slug(name: str, max_words: int = 4) -> str:
    stem = _JUNK.sub("", Path(name).stem)
    words = [w.lower() for w in _STRIP.split(stem.strip()) if len(w) > 2][:max_words]
    return "-".join(words) if words else "untitled"
