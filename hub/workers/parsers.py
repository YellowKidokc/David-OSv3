"""Deterministic file metadata parsers for classification and future rename/tag lanes."""
from __future__ import annotations

import csv
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def parse_file_metadata(path: str) -> dict[str, object]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".pdf" or _starts_with(file_path, b"%PDF-"):
        return parse_pdf_metadata(file_path)
    if suffix == ".docx":
        return parse_office_zip_metadata(file_path, document_type="docx")
    if suffix == ".xlsx":
        return parse_office_zip_metadata(file_path, document_type="xlsx")
    if suffix == ".csv":
        return parse_csv_metadata(file_path)
    if suffix in {".png", ".jpg", ".jpeg", ".gif"}:
        return parse_image_metadata(file_path)
    return {"parser": "none", "metadata": {}}


def parse_pdf_metadata(path: Path) -> dict[str, object]:
    head = _read_head(path, 2048)
    version = None
    if head.startswith(b"%PDF-"):
        version = head[:8].decode("latin-1", errors="ignore").replace("%PDF-", "")
    return {"parser": "pdf", "metadata": {"pdf_version": version, "is_pdf": head.startswith(b"%PDF-")}}


def parse_office_zip_metadata(path: Path, *, document_type: str) -> dict[str, object]:
    metadata: dict[str, object] = {"document_type": document_type, "is_zip_package": False}
    if not zipfile.is_zipfile(path):
        return {"parser": document_type, "metadata": metadata}
    metadata["is_zip_package"] = True
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        metadata["part_count"] = len(names)
        core = _read_zip_xml(archive, "docProps/core.xml")
        if core is not None:
            metadata.update(_office_core_properties(core))
        if document_type == "xlsx":
            metadata["sheet_count"] = len([name for name in names if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")])
        if document_type == "docx":
            document = _read_zip_xml(archive, "word/document.xml")
            if document is not None:
                metadata["paragraph_count"] = len(document.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"))
    return {"parser": document_type, "metadata": metadata}


def parse_csv_metadata(path: Path) -> dict[str, object]:
    sample = path.read_text(encoding="utf-8", errors="replace")[:8192]
    if sample.strip():
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
    else:
        dialect = csv.excel
    rows = list(csv.reader(sample.splitlines(), dialect))[:25]
    column_count = max((len(row) for row in rows), default=0)
    return {"parser": "csv", "metadata": {"sample_rows": len(rows), "sample_columns": column_count, "delimiter": dialect.delimiter}}


def parse_image_metadata(path: Path) -> dict[str, object]:
    head = _read_head(path, 64)
    if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
        width, height = struct.unpack(">II", head[16:24])
        return {"parser": "image", "metadata": {"format": "png", "width": width, "height": height}}
    if head.startswith((b"GIF87a", b"GIF89a")) and len(head) >= 10:
        width, height = struct.unpack("<HH", head[6:10])
        return {"parser": "image", "metadata": {"format": "gif", "width": width, "height": height}}
    if head.startswith(b"\xff\xd8\xff"):
        return {"parser": "image", "metadata": {"format": "jpeg"}}
    return {"parser": "image", "metadata": {"format": "unknown"}}


def _read_head(path: Path, size: int = 4096) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def _starts_with(path: Path, prefix: bytes) -> bool:
    return _read_head(path, len(prefix)).startswith(prefix)


def _read_zip_xml(archive: zipfile.ZipFile, name: str) -> ElementTree.Element | None:
    if name not in archive.namelist():
        return None
    with archive.open(name) as handle:
        return ElementTree.fromstring(handle.read())


def _office_core_properties(root: ElementTree.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"title", "creator", "created", "modified"} and element.text:
            values[tag] = element.text
    return values
