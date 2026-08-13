import tempfile
from pathlib import Path

from fis.federation import Federation
from fis.lineage import Lineage


def _territory(name, files):
    db = Path(tempfile.mkdtemp()) / "territory.sqlite"
    lin = Lineage(db)
    for path in files:
        lin.register(kind="spreadsheet", ext="xlsx", path=path, project="PROJECT-MDA")
    lin.close()
    return db


def _fed():
    return Federation(Path(tempfile.mkdtemp()) / "catalog.sqlite")


def test_searches_all_territories_origin_tagged():
    h = _territory("H", ["H:/Research/MDA/master.xlsx"])
    z = _territory("Z", ["Z:/Archive/MDA/decline_v7.xlsx"])
    fed = _fed()
    fed.register_territory("T003", "H Drive", h)
    fed.register_territory("T004", "Z Drive", z)
    res = fed.search_all("MDA")
    origins = {r["origin"] for r in res["results"]}
    assert any(o.startswith("T003:") for o in origins)
    assert any(o.startswith("T004:") for o in origins)
    assert res["complete"] is True
    assert res["query_run"].startswith("QR-")


def test_offline_territory_marks_incomplete_not_faked():
    h = _territory("H", ["H:/MDA/a.xlsx"])
    fed = _fed()
    fed.register_territory("T003", "H Drive", h)
    fed.register_territory("T004", "Z Drive", "Z:/does/not/exist/territory.sqlite")
    res = fed.search_all("MDA")
    assert res["territories"]["T004"] == "unavailable"
    assert res["complete"] is False                     # never claims it searched everything


def test_results_are_deterministically_ordered():
    a = _territory("A", ["H:/MDA/a.xlsx", "H:/MDA/b.xlsx"])
    fed = _fed()
    fed.register_territory("T001", "A", a)
    r1 = [r["origin"] for r in fed.search_all("MDA")["results"]]
    r2 = [r["origin"] for r in fed.search_all("MDA")["results"]]
    assert r1 == r2 and r1 == sorted(r1)                # stable, sorted


def test_snapshot_records_sequences():
    h = _territory("H", ["H:/MDA/a.xlsx"])
    fed = _fed()
    fed.register_territory("T003", "H Drive", h)
    res = fed.search_all("MDA")
    assert res["territories"]["T003"].startswith("seq_")
