"""Folder Intelligence System symptom detectors."""
from pathlib import Path
from .models import Severity,SymptomReport,SymptomResult
from .structural import *
from .content import *
from .temporal import *
from .infrastructure import *
from .naming import *
from .research import *

DETECTORS=(detect_ext_swamp,detect_version_sprawl,detect_depth_explosion,detect_flat_overload,detect_orphan_sidecar,detect_naming_collision,detect_project_scatter,detect_phantom_refs,detect_duplicates,detect_format_redundancy,detect_draft_graveyard,detect_doc_chaos,detect_media_dump,detect_unknown_blobs,detect_encoding_chaos,detect_thin_content,detect_incomplete_extract,detect_time_bombs,detect_burst_dump,detect_stale_pipeline,detect_abandoned_workspace,detect_program_root,detect_toolchain_residue,detect_config_leak,detect_sync_ghost,detect_repo_mix,detect_mirror_drift,detect_broken_shortcuts,detect_log_accumulation,detect_name_rot,detect_download_purgatory,detect_tiny_debris,detect_path_length,detect_untagged_canonical,detect_ai_debris,detect_cross_purpose,detect_mixed_provenance,detect_archive_pile,detect_chi_gaps,detect_law_holes,detect_claim_gaps)

def run_all_symptoms(folder_path) -> SymptomReport:
    path=Path(folder_path).expanduser().resolve()
    if not path.is_dir(): raise NotADirectoryError(path)
    report=SymptomReport(path)
    for detector in DETECTORS:
        try: report.results.extend(detector(path))
        except (OSError,UnicodeError) as exc: report.errors.append(f"{detector.__name__}: {exc}")
    report.results.sort(key=lambda item:(item.symptom_id,str(item.path),item.message))
    return report

__all__=["Severity","SymptomResult","SymptomReport","DETECTORS","run_all_symptoms"]+[f.__name__ for f in DETECTORS]
