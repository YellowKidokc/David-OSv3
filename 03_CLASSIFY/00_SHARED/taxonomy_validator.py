"""
Taxonomy Validator & Closed Vocabulary Engine (v0.4)
Enforces TAG_TAXONOMY_v0.4.md rules:
- Part A: facet prefixes: ct-, rc-, ep-, wf-, subject domain prefixes
- Part A: closed domains and content types, reserved system tags
- Part B: mim.v1 sidecar cards (fields, standing vocabulary, subject = filename = H1)

CLI:  python taxonomy_validator.py <sidecars folder>
"""

from pathlib import Path
import re

SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR / "TEMPLATES"

VALID_CONTENT_TYPES = {
    "ct-argument", "ct-narrative", "ct-overview", "ct-equation",
    "ct-method", "ct-reference", "ct-implications", "ct-status",
    "ct-outline", "ct-source"
}

VALID_READER_CATEGORIES = {
    "rc-general", "rc-curious", "rc-student", "rc-technical",
    "rc-specialist", "rc-internal"
}

VALID_EPISTEMIC_ROLES = {
    "ep-evidence", "ep-prediction", "ep-audit", "ep-adversarial",
    "ep-consilience", "ep-defeated", "ep-open", "ep-rigor",
    "ep-uniqueness", "ep-falsifiable"
}

VALID_DOMAINS = {
    "physics", "theology", "mathematics", "consciousness", "information",
    "theophysics", "philosophy", "cosmology", "thermodynamics", "quantum",
    "ethics", "scripture", "history", "epistemology", "system", "general"
}

def clean_tag(raw_tag: str) -> str:
    """Normalize tag to lowercase kebab-case."""
    tag = raw_tag.strip().lower()
    tag = re.sub(r"[^\w\-]", "-", tag)
    tag = re.sub(r"-+", "-", tag).strip("-")
    return tag

def validate_tags(tag_list: list[str]) -> list[str]:
    """Validate and clean list of tags."""
    cleaned = []
    for t in tag_list:
        ct = clean_tag(t)
        if ct and ct not in cleaned:
            cleaned.append(ct)
    return cleaned

def validate_domain(domain: str) -> str:
    d = clean_tag(domain)
    return d if d in VALID_DOMAINS else "theophysics"

def validate_content_type(ct: str) -> str:
    c = clean_tag(ct)
    if not c.startswith("ct-"):
        c = f"ct-{c}"
    return c if c in VALID_CONTENT_TYPES else "ct-argument"

def validate_reader_category(rc: str) -> str:
    r = clean_tag(rc)
    if not r.startswith("rc-"):
        r = f"rc-{r}"
    return r if r in VALID_READER_CATEGORIES else "rc-technical"


# --- v0.4: Part B sidecar validation ---------------------------------------

RESERVED_TAGS = {"sidecar", "subject"}

VALID_STANDING = {
    "declaration", "canon", "freeze-candidate", "proposed",
    "draft", "reference", "superseded", "inert",
}

VALID_SUBJECT_PREFIXES = (
    "tp-", "theo-", "phil-", "math-", "phys-", "info-", "cog-",
    "soc-", "meth-", "cs-", "wf-", "series-",
)

REQUIRED_CARD_FIELDS = ("sidecar", "subject", "source", "source_file", "standing", "folder_class")
SUBJECT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .\-]*$")


def validate_standing(standing: str) -> bool:
    return clean_tag(standing) in VALID_STANDING


def _parse_frontmatter(text: str) -> tuple[dict, list[str], str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, [], text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, [], text
    fields, tags, in_tags = {}, [], False
    for line in lines[1:end]:
        if in_tags and line.strip().startswith("- "):
            tags.append(line.strip()[2:].strip())
            continue
        in_tags = False
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            k, v = k.strip(), v.split(" #")[0].strip().strip('"')
            if k == "tags":
                in_tags = True
            else:
                fields[k] = v
    return fields, tags, "\n".join(lines[end + 1:])


def validate_sidecar_card(path) -> list[str]:
    """Return a list of problems for one mim.v1 card (empty list = valid)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r", "")
    fields, tags, body = _parse_frontmatter(text)
    if fields.get("type") == "subject-index":
        return []
    problems = [f"missing field: {f}" for f in REQUIRED_CARD_FIELDS if not fields.get(f)]
    if fields.get("sidecar") and fields["sidecar"] != "mim.v1":
        problems.append(f"sidecar is {fields['sidecar']!r}, expected 'mim.v1'")
    standing = fields.get("standing", "")
    if standing and not validate_standing(standing):
        hint = " (version number - move to version:)" if re.match(r"^v?\d", standing) else ""
        problems.append(f"standing {standing!r} not in closed vocabulary{hint}")
    subject = fields.get("subject", "")
    if subject and subject != path.stem:
        problems.append(f"subject {subject!r} != filename {path.stem!r}")
    if subject and not SUBJECT_NAME_RE.match(subject):
        problems.append(f"subject {subject!r} has illegal characters")
    h1 = next((l[2:].strip() for l in body.split("\n") if l.startswith("# ")), "")
    if subject and h1 != subject:
        problems.append(f"H1 {h1!r} != subject {subject!r}")
    problems += [f"missing reserved tag: {t}" for t in sorted(RESERVED_TAGS) if t not in tags]
    for t in tags:
        if t in RESERVED_TAGS:
            continue
        if not (t in VALID_CONTENT_TYPES or t in VALID_READER_CATEGORIES
                or t in VALID_EPISTEMIC_ROLES or t.startswith(VALID_SUBJECT_PREFIXES)):
            problems.append(f"tag {t!r} not on the closed list")
    src = fields.get("source", "").strip("[]")
    if src and f"Read [[{src}]]." not in body:
        problems.append("body missing closing 'Read [[source]].' line")
    return problems


def validate_sidecar_folder(folder) -> dict[str, list[str]]:
    """Validate every card in a sidecars/ folder. Returns {filename: problems} for failures."""
    results = {p.name: validate_sidecar_card(p) for p in sorted(Path(folder).glob("*.md"))}
    return {name: probs for name, probs in results.items() if probs}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("usage: python taxonomy_validator.py <sidecars folder>")
    folder = Path(sys.argv[1])
    failures = validate_sidecar_folder(folder)
    total = len(list(folder.glob("*.md")))
    for name, probs in failures.items():
        print(f"FAIL {name}")
        for pr in probs:
            print(f"     - {pr}")
    print(f"\n{total - len(failures)}/{total} cards valid")
    sys.exit(1 if failures else 0)
