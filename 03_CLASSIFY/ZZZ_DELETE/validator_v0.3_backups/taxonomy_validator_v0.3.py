"""
Taxonomy Validator & Closed Vocabulary Engine (v0.3)
Enforces 01_TAG_TAXONOMY_v0.3.md rules:
- Facet prefixes: ct-, rc-, ep-, wf-, subject domain prefixes
- Closed domains and content types
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
