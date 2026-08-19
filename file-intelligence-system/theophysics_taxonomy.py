"""Canonical Theophysics filename grammar shared by FIS namer and sidecars."""
import json
import os
import re
from datetime import datetime
from pathlib import Path

TAXONOMY_PATH = Path(__file__).with_name("config") / "theophysics_filename_taxonomy.json"
_TAXONOMY = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
DOMAINS = _TAXONOMY["domains"]
TYPES = _TAXONOMY["types"]
DOMAIN_ALIASES = {k.lower(): v for k, v in _TAXONOMY["aliases"].items()}
TYPE_ALIASES = {k.lower(): v for k, v in _TAXONOMY["type_aliases"].items()}
CANONICAL_RE = re.compile(r"^(?P<domain>[A-Z]{3})_(?P<type>[A-Z]{3})_(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)_(?P<date>\d{8})(?P<ext>\.[^.]+)?$")

def taxonomy() -> dict:
    return _TAXONOMY

def resolve_domain(value: str, default: str = "TPH") -> str:
    value = (value or "").strip()
    return value.upper() if value.upper() in DOMAINS else DOMAIN_ALIASES.get(value.lower(), default)

def resolve_type(value: str, default: str = "ART") -> str:
    value = (value or "").strip()
    return value.upper() if value.upper() in TYPES else TYPE_ALIASES.get(value.lower(), default)

def slugify(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return (value or "untitled")[:max_len].strip("-") or "untitled"

def build_filename(domain: str, type_code: str, title: str, date_value: datetime, extension: str = "") -> str:
    ext = extension if extension.startswith(".") or not extension else f".{extension}"
    return f"{resolve_domain(domain)}_{resolve_type(type_code)}_{slugify(title)}_{date_value:%Y%m%d}{ext.lower()}"

def parse_filename(name: str) -> dict | None:
    match = CANONICAL_RE.match(Path(name).name)
    if not match or match.group("domain") not in DOMAINS or match.group("type") not in TYPES:
        return None
    result = match.groupdict()
    result.update({
        "domain_code": result["domain"],
        "type_code": result["type"],
        "domain": DOMAINS[result["domain"]],
        "type": TYPES[result["type"]],
    })
    return result

def grammar_mode() -> str:
    return os.environ.get("FIS_NAMING_GRAMMAR", "canonical").strip().lower()
