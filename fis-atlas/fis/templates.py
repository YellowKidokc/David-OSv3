"""Job templates — one reusable recipe, fill in the blanks.

A template is a parameterized JobSpec. "Find a series across drives, collect,
flatten, dedupe, organize" is ONE template; a new task only changes roots,
concept, aliases, destination. Compiles to a FileJob for the universal engine.
"""
from __future__ import annotations

from pathlib import Path

try:
    import yaml
except Exception:                       # pragma: no cover
    yaml = None

from .engine import FileJob, Operation, Strategy

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_STRAT = {"flat": Strategy.FLAT, "by_extension": Strategy.EXTENSION,
          "semantic_categories": Strategy.SEMANTIC, "series_then_format": Strategy.SERIES_THEN_FORMAT}
_OPS = {o.value: o for o in Operation}


def load_template(template_id: str) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required to load templates")
    path = TEMPLATES_DIR / f"{template_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no template: {template_id}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def instantiate(template: dict, *, roots: list[str], destination: str,
                concept: str | None = None, aliases: list[str] | None = None,
                job_id: str = "JOB-0001", **overrides) -> FileJob:
    """Fill a template's blanks and compile to a FileJob (preview-only by default)."""
    p = dict(template.get("params", {}))
    concept = concept or p.get("concept", "collection")
    aliases = aliases or p.get("aliases", [concept])
    ops = [_OPS[o] for o in template.get("operations", []) if o in _OPS] or [Operation.SCAN]
    spec = dict(
        job_id=job_id,
        name=template.get("name", "Job").replace("{{concept}}", concept),
        roots=roots, destination=destination, operations=ops,
        strategy=_STRAT.get(template.get("strategy", "series_then_format"), Strategy.SERIES_THEN_FORMAT),
        aliases=aliases,
        accept_threshold=template.get("accept_threshold", 0.6),
        review_threshold=template.get("review_threshold", 0.2),
        preserve_originals=template.get("preserve_originals", True),
        flatten=template.get("flatten", True),
        exact_dedupe=template.get("exact_dedupe", True),
        apply=False, approved=False,
    )
    spec.update(overrides)
    return FileJob(**spec)


def build(template_id: str, **kw) -> FileJob:
    return instantiate(load_template(template_id), **kw)
