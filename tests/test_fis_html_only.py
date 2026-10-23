import importlib.util
from pathlib import Path
import sys


def _load_renderer():
    path = Path(__file__).resolve().parents[1] / "file-intelligence-system" / "fis_folder_memory.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("fis_folder_memory_html_only", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_scan_always_writes_recursive_html_and_never_fisnotes(tmp_path):
    renderer = _load_renderer()
    root = tmp_path / "vault"
    child = root / "Axiom"
    child.mkdir(parents=True)
    (root / "root.md").write_text("Master Equation", encoding="utf-8")
    (root / "MASTER_EQUATION_LOSSLESS_AI_MANIFEST.md").write_text(
        "MASTER_EQUATION_CHI\nADDRESS =\nTHEOPHYSICS_FORMAL/MASTER_EQUATION_CHI/CANONICAL_LOCAL_AND_INTEGRATED_FORM/AI_INTERNAL_REVIEW/BIND/R3\n:: G3 M3 E3 S3 T3 K3 R3 Q3 F3 C3\n:: [G.C] [M.F] [E.Q] [S.R] [T.K]\n",
        encoding="utf-8",
    )
    (child / "axiom.md").write_text("God", encoding="utf-8")

    renderer.scan(
        root=root,
        db_path=tmp_path / "fis.sqlite",
        recursive=False,
        write=True,
        html=False,
        local_ai=False,
        ai_limit=0,
        ai_model="unused",
        file_notes=True,
        cleanup_stale=True,
        wipe_fisnotes=True,
    )

    assert (root / "FIS.html").exists()
    assert (child / "FIS.html").exists()
    assert "FIS FOLDER BRAIN v2.1 / RECURSIVE SEMANTIC VIEW" in (root / "FIS.html").read_text(encoding="utf-8")
    html = (root / "FIS.html").read_text(encoding="utf-8")
    assert "MASTER_EQUATION_CHI__CANONICAL_LOCAL_AND_INTEGRATED_FORM__R3" in html
    assert "declared by MASTER_EQUATION_LOSSLESS_AI_MANIFEST.md" in html
    assert not list(root.rglob("*.fisnote"))
