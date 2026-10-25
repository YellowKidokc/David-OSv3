"""Pure helpers extracted from 03_CLASSIFY/03_RENAMING/rename_engine.py; originals preserved."""
import re
ROMAN = re.compile(r"^[ivx]+[a-z]?$")
def _rx(word: str) -> re.Pattern:
    w = re.escape(word.lower()).replace(r"\ ", r"[\s_\-]+")
    return re.compile(rf"\b{w}\b" if len(word) <= 4 else rf"\b{w}")


def _match(table: list[dict], name: str, title: str, body: str,
           folder: str = "") -> tuple[str, str, float] | None:
    """Name beats title beats folder beats body. In name/title/folder the first rule wins (rule
    order = priority); in the body the rule mentioned most often wins, with at least 3 mentions."""
    for where, text, weight in (("name", name, 0.35), ("title", title, 0.25), ("folder", folder, 0.20)):
        for rule in table:
            for w in rule["words"]:
                if _rx(w).search(text):
                    return rule["code"], f"{rule['code']} ← '{w}' in {where}", weight
    if body:
        counts = {r["code"]: sum(len(_rx(w).findall(body)) for w in r["words"]) for r in table}
        code, n = max(counts.items(), key=lambda kv: kv[1])
        if n >= 3:
            return code, f"{code} ← mentioned {n}× in text", 0.12
    return None


def _clean(text: str) -> str:
    text = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
    text = text.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _words(stem: str, title: str, rules: dict) -> tuple[str, list[str]]:
    why, s = [], _clean(stem)
    lead = ""
    for sr in rules["series"]:
        m = re.match(sr["pattern"], stem.lower().replace(" - ", "_"))
        if m:
            n = m.group(1)
            x = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            lead = sr["as"].replace("{n}", f"{int(n):02d}").replace("{x}", x or "")
            s = _clean(stem.lower().replace(" - ", "_")[m.end():])
            why.append(f"order kept: {lead}")
            break
    drop = set(rules["drop_words"])
    words = [w for w in s.split() if w not in drop and len(w) > 1 and not ROMAN.match(w)]
    if len(words) < 2 and title:
        words = [w for w in _clean(title).split() if w not in drop and len(w) > 1][:rules["max_words"]]
        why.append("words from title")
    words = words[:rules["max_words"]]
    out = "_".join(([lead] if lead else []) + words) or "untitled"
    return out, why
