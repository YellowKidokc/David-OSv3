from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fis_html_index import connect, fts_query, list_series, scan_root


def test_scan_search_and_series_gap(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "drv-00-start.html").write_text(
        '<html><head><title>Start</title><meta name="keywords" content="truth, architecture"></head>'
        '<body><h1>The Argument</h1><p>Truth has a continuity structure.</p><a rel="next" href="drv-02-end.html">Next</a></body></html>',
        encoding="utf-8",
    )
    (root / "drv-02-end.html").write_text(
        '<html><head><title>End</title></head><body><h1>The Lock</h1><p>Architecture closes the cycle.</p></body></html>',
        encoding="utf-8",
    )
    db = tmp_path / "fis.sqlite"
    result = scan_root(db, root)
    assert result["html_count"] == 2
    assert result["error_count"] == 0
    conn = connect(db)
    assert fts_query(conn, "continuity structure")[0]["title"] == "Start"
    series = list_series(conn)
    assert series[0]["series_key"] == "drv"
    assert series[0]["missing_parts"] == [1]
    assert conn.execute("SELECT count(*) FROM continuity WHERE relation='gap'").fetchone()[0] == 1
    conn.close()

