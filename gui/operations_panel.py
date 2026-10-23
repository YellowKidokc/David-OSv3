#!/usr/bin/env python3
"""Operations panel — a button surface over the generic David-OS engine.

Nothing here implements file logic. Every button calls an existing engine module:

  engine.symptoms            folder health, including C09 thin/empty content
  engine.reference_index     who links to whom; broken links; repointing after moves
  engine.quality_score       writing-quality snapshot and before/after comparison
  engine.canon_sidecar       freeze pre-canon versions to sidecars + one zip
  hub.workers.file_action    move / rename / archive / delete / undo, dry-run first
  engine.path_write_policy   protected roots, so a scan can never write into a folder

Runs standalone (``python gui/operations_panel.py``) or mounts as a tab in
fis_scanner_gui.
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget,
)

REPO = Path(__file__).resolve().parents[1]
for extra in (REPO, REPO / "engine"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from engine import aggregate_report, canon_sidecar, priority_roots, quality_score, reference_index  # noqa: E402
from engine import path_write_policy  # noqa: E402
from engine.symptoms import run_all_symptoms  # noqa: E402
from hub.workers.file_action_worker import execute_file_action, read_journal  # noqa: E402

RUNS = REPO / "runs"


class Job(QThread):
    """Runs one engine call off the UI thread."""

    done = Signal(object)
    failed = Signal(str)
    note = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def run(self):
        try:
            self.done.emit(self._fn(*self._args, **self._kwargs))
        except Exception:
            self.failed.emit(traceback.format_exc(limit=4))


class OperationsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._job: Job | None = None
        self._rows: list[dict] = []
        self._last_report: dict | None = None
        self._build()

    # ── layout ──────────────────────────────────────────────
    def _build(self) -> None:
        outer = QVBoxLayout(self)

        target = QGroupBox("Folder")
        row = QHBoxLayout(target)
        self.folder = QLineEdit(r"G:\faiththruphysics-site-v2")
        self.folder.setFont(QFont("Consolas", 10))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.read_only = QCheckBox("Read-only (never write into this folder)")
        self.read_only.setChecked(True)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        row.addWidget(self.read_only)
        outer.addWidget(target)

        scans = QGroupBox("Look at it")
        scan_row = QHBoxLayout(scans)
        for label, slot in (
            ("Health scan", self._scan_health),
            ("Thin / empty files", self._scan_thin),
            ("Link map + broken links", self._scan_links),
            ("Quality snapshot", self._snapshot),
            ("Compare snapshots", self._compare),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            scan_row.addWidget(button)
        outer.addWidget(scans)

        priority = QGroupBox("High-priority places — declared once, respected by every scan")
        prio = QHBoxLayout(priority)
        self.priority_mode = QComboBox()
        self.priority_mode.addItems(list(priority_roots.MODES))
        self.priority_label = QLineEdit()
        self.priority_label.setPlaceholderText("label, e.g. LIVE SITE / CANON / DO NOT TOUCH")
        for label, slot in (("Flag this folder", self._priority_add),
                            ("Unflag", self._priority_remove),
                            ("List", self._priority_list)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            prio.addWidget(button)
        prio.addWidget(QLabel("mode:"))
        prio.addWidget(self.priority_mode)
        prio.addWidget(self.priority_label, 1)
        outer.addWidget(priority)

        bundle = QGroupBox("Aggregate + export — one bundle for the report and for handing to another model")
        bun = QHBoxLayout(bundle)
        self.export_dir = QLineEdit(str(aggregate_report.DEFAULT_EXPORT))
        self.export_dir.setFont(QFont("Consolas", 9))
        export_browse = QPushButton("…")
        export_browse.setMaximumWidth(32)
        export_browse.clicked.connect(self._browse_export)
        deep = QPushButton("DEEP SCAN + VISUAL REPORT")
        deep.clicked.connect(self._deep_scan)
        open_folder = QPushButton("Open export folder")
        open_folder.clicked.connect(self._open_export)
        bun.addWidget(QLabel("Export to:"))
        bun.addWidget(self.export_dir, 1)
        bun.addWidget(export_browse)
        bun.addWidget(deep)
        bun.addWidget(open_folder)
        outer.addWidget(bundle)

        actions = QGroupBox("Change it — dry run first, every action reversible")
        act = QVBoxLayout(actions)
        top = QHBoxLayout()
        self.action = QComboBox()
        self.action.addItems(["archive", "move", "rename", "delete", "copy"])
        top.addWidget(QLabel("Action:"))
        top.addWidget(self.action)
        self.destination = QLineEdit(str(RUNS / "quarantine"))
        self.destination.setFont(QFont("Consolas", 9))
        top.addWidget(QLabel("Destination:"), 0)
        top.addWidget(self.destination, 1)
        dest_browse = QPushButton("…")
        dest_browse.setMaximumWidth(32)
        dest_browse.clicked.connect(self._browse_dest)
        top.addWidget(dest_browse)
        self.fix_links = QCheckBox("Repoint links afterwards")
        self.fix_links.setChecked(True)
        top.addWidget(self.fix_links)
        act.addLayout(top)

        buttons = QHBoxLayout()
        for label, slot in (
            ("Preview on selected", lambda: self._apply(dry=True)),
            ("APPLY to selected", lambda: self._apply(dry=False)),
            ("Freeze canon + zip versions", self._freeze),
            ("Undo last", self._undo),
            ("Show journal", self._journal),
            ("Export report", self._export),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        self.undo_count = QSpinBox()
        self.undo_count.setRange(1, 500)
        self.undo_count.setValue(1)
        buttons.addWidget(QLabel("undo N:"))
        buttons.addWidget(self.undo_count)
        act.addLayout(buttons)
        outer.addWidget(actions)

        split = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "File", "Finding", "Detail", "Score"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        split.addWidget(self.table)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        split.addWidget(self.log)
        split.setSizes([460, 240])
        outer.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.select_all = QPushButton("Select all")
        self.select_all.clicked.connect(lambda: self._set_all(True))
        self.select_none = QPushButton("Select none")
        self.select_none.clicked.connect(lambda: self._set_all(False))
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        bottom.addWidget(self.select_all)
        bottom.addWidget(self.select_none)
        bottom.addWidget(self.progress, 1)
        self.status = QLabel("Ready.")
        bottom.addWidget(self.status)
        outer.addLayout(bottom)

    # ── helpers ─────────────────────────────────────────────
    def _root(self) -> Path:
        return Path(self.folder.text().strip())

    def _say(self, text: str) -> None:
        self.log.append(f"[{datetime.now():%H:%M:%S}] {text}")

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder")
        if chosen:
            self.folder.setText(chosen)

    def _browse_dest(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose destination")
        if chosen:
            self.destination.setText(chosen)

    def _guard(self) -> None:
        path_write_policy.clear_protected_roots()
        if self.read_only.isChecked():
            path_write_policy.protect_root(self._root())

    def _start(self, label: str, fn, *args, **kwargs) -> None:
        if self._job and self._job.isRunning():
            QMessageBox.information(self, "Busy", "A job is already running.")
            return
        root = self._root()
        if not root.is_dir():
            QMessageBox.warning(self, "No folder", f"{root} is not a folder.")
            return
        self._guard()
        self._say(f"{label} — {root}")
        self.status.setText(label + "…")
        self.progress.show()
        self._job = Job(fn, *args, **kwargs)
        self._job.done.connect(lambda payload, name=label: self._finished(name, payload))
        self._job.failed.connect(self._errored)
        self._job.start()

    def _finished(self, label: str, payload) -> None:
        self.progress.hide()
        self.status.setText(f"{label} — done")
        handler = getattr(self, f"_render_{label.lower().replace(' ', '_').replace('/', '_')}", None)
        if handler:
            handler(payload)
        else:
            self._say(json.dumps(payload, default=str)[:4000])

    def _errored(self, message: str) -> None:
        self.progress.hide()
        self.status.setText("Failed")
        self._say(message)

    def _fill(self, rows: list[dict]) -> None:
        self._rows = rows
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Unchecked)
            self.table.setItem(index, 0, check)
            for column, key in enumerate(("file", "finding", "detail", "score"), start=1):
                self.table.setItem(index, column, QTableWidgetItem(str(row.get(key, ""))))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _set_all(self, checked: bool) -> None:
        for index in range(self.table.rowCount()):
            item = self.table.item(index, 0)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _selected(self) -> list[Path]:
        picked = []
        for index in range(self.table.rowCount()):
            item = self.table.item(index, 0)
            if item and item.checkState() == Qt.Checked:
                picked.append(Path(self._rows[index]["file"]))
        return picked

    # ── scans ───────────────────────────────────────────────
    def _scan_health(self) -> None:
        self._start("Health scan", lambda root: run_all_symptoms(root).to_dict(), self._root())

    def _render_health_scan(self, payload: dict) -> None:
        self._last_report = payload
        rows = [{"file": r["path"], "finding": f'{r["symptom_id"]} {r["name"]}',
                 "detail": r["message"], "score": r["severity"]} for r in payload["results"]]
        self._fill(rows)
        self._say(f"{payload['count']} findings — {payload['by_severity']}")

    def _scan_thin(self) -> None:
        from engine.symptoms.content import detect_thin_content
        self._start("Thin files", lambda root: [r.to_dict() for r in detect_thin_content(root)], self._root())

    def _render_thin_files(self, payload: list[dict]) -> None:
        self._fill([{"file": r["path"], "finding": "Thin content", "detail": r["message"],
                     "score": r["evidence"].get("words", "")} for r in payload])
        self._say(f"{len(payload)} empty or near-empty files. Tick the ones to archive.")

    def _scan_links(self) -> None:
        self._start("Link map", lambda root: reference_index.build_index(root).to_dict(), self._root())

    def _render_link_map(self, payload: dict) -> None:
        self._fill([{"file": b["from"], "finding": "Broken reference", "detail": b["ref"], "score": ""}
                    for b in payload["broken"]])
        self._say(f"{payload['files_scanned']} files scanned, {payload['targets']} targets, "
                  f"{len(payload['broken'])} broken references.")

    def _snapshot(self) -> None:
        self._start("Quality snapshot", quality_score.snapshot, self._root())

    def _render_quality_snapshot(self, payload: dict) -> None:
        self._last_report = payload
        self._fill([{"file": s["path"], "finding": f'grade {s["grade"]}',
                     "detail": "; ".join(s["reasons"]) or "clean", "score": s["score"]}
                    for s in payload["scores"]])
        out = RUNS / "quality"
        out.mkdir(parents=True, exist_ok=True)
        saved = out / f"quality_snapshot_{datetime.now():%Y%m%d_%H%M%S}.json"
        saved.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._say(f"{payload['files']} files, mean {payload['mean_score']}, grades {payload['grades']}")
        self._say(f"Snapshot saved: {saved}")

    def _compare(self) -> None:
        first, _ = QFileDialog.getOpenFileName(self, "Earlier snapshot", str(RUNS / "quality"), "JSON (*.json)")
        if not first:
            return
        second, _ = QFileDialog.getOpenFileName(self, "Later snapshot", str(RUNS / "quality"), "JSON (*.json)")
        if not second:
            return
        result = quality_score.compare(first, second)
        self._fill([{"file": m["path"], "finding": "improved" if m["delta"] > 0 else "worsened",
                     "detail": f'{m["from"]} → {m["to"]}', "score": m["delta"]}
                    for m in result["improved"] + result["worsened"]])
        self._say(f"mean {result['mean_before']} → {result['mean_after']}; "
                  f"{len(result['improved'])} improved, {len(result['worsened'])} worse")

    # ── priority roots ──────────────────────────────────────
    def _priority_add(self) -> None:
        mode, label = self.priority_mode.currentText(), self.priority_label.text().strip()
        priority_roots.add(self._root(), mode=mode, label=label)
        self._say(f"Priority root added: [{mode}] {self._root()} {('— ' + label) if label else ''}")
        self._priority_list()

    def _priority_remove(self) -> None:
        priority_roots.remove(self._root())
        self._say(f"Priority root removed: {self._root()}")
        self._priority_list()

    def _priority_list(self) -> None:
        roots = priority_roots.load()
        self._fill([{"file": r.path, "finding": r.mode, "detail": r.label or r.note, "score": ""}
                    for r in roots])
        self._say(f"{len(roots)} priority root(s) declared → {priority_roots.CONFIG}")

    # ── aggregate ───────────────────────────────────────────
    def _browse_export(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Export destination", self.export_dir.text())
        if chosen:
            self.export_dir.setText(chosen)

    def _deep_scan(self) -> None:
        self._start("Deep scan", aggregate_report.run, self._root(), self.export_dir.text().strip())

    def _render_deep_scan(self, payload: dict) -> None:
        self._last_export = payload
        self._say(f"Bundle written → {payload['folder']}")
        for key in ("html", "bundle", "anomalies", "files", "handoff"):
            self._say(f"  {key}: {Path(payload[key]).name}")
        self._say(f"{payload['anomaly_count']} probable mistakes found. Opening the visual report.")
        try:
            import webbrowser
            webbrowser.open(Path(payload["html"]).as_uri())
        except Exception as exc:
            self._say(f"(could not open browser: {exc})")

    def _open_export(self) -> None:
        folder = Path(getattr(self, "_last_export", {}).get("folder", self.export_dir.text().strip()))
        if folder.exists():
            execute_file_action({"action": "open", "source_path": str(folder)})
        else:
            QMessageBox.information(self, "Not there yet", f"{folder} does not exist.")

    # ── actions ─────────────────────────────────────────────
    def _apply(self, *, dry: bool) -> None:
        picked = self._selected()
        if not picked:
            QMessageBox.information(self, "Nothing selected", "Tick some rows first.")
            return
        if not dry and self.read_only.isChecked():
            QMessageBox.warning(self, "Read-only", "Untick read-only to change files in this folder.")
            return
        if not dry:
            confirm = QMessageBox.question(
                self, "Apply", f"{self.action.currentText()} {len(picked)} file(s)?\nThis is reversible with Undo.")
            if confirm != QMessageBox.Yes:
                return
        self._guard()
        action, destination = self.action.currentText(), Path(self.destination.text().strip())
        moves, results = {}, []
        for source in picked:
            payload = {"action": action, "source_path": str(source), "dry_run": dry}
            if action in {"archive", "move", "rename", "copy"}:
                payload["target_path"] = str(destination / source.name)
            try:
                outcome = execute_file_action(payload)
                results.append(outcome)
                if action in {"archive", "move", "rename"} and outcome.get("target_path"):
                    moves[source] = Path(str(outcome["target_path"]))
            except Exception as exc:
                self._say(f"{source.name}: {exc}")
        self._say(f"{'Preview' if dry else 'Applied'}: {len(results)} {action} action(s) → {destination}")
        if moves and self.fix_links.isChecked():
            index = reference_index.build_index(self._root())
            rewrite = reference_index.rewrite_references(index, moves, dry_run=dry)
            self._say(f"Links: {rewrite['files_edited']} file(s) {'would be' if dry else ''} repointed")

    def _freeze(self) -> None:
        picked = self._selected()
        if not picked:
            QMessageBox.information(self, "Nothing selected", "Tick the versions to freeze.")
            return
        keeper = picked[0]
        group = canon_sidecar.CanonGroup(keeper, picked, reason="chosen in Operations panel")
        dry = self.read_only.isChecked()
        result = canon_sidecar.freeze([group], RUNS / "canon", dry_run=dry)
        self._say(f"Canon freeze ({'preview' if dry else 'written'}): keeper {keeper.name}, "
                  f"{result['versions_recorded']} version(s) recorded, archive {result['archive']}")

    def _undo(self) -> None:
        result = execute_file_action({"action": "undo", "count": self.undo_count.value(),
                                      "dry_run": self.read_only.isChecked()})
        self._say(f"Undo: {result['count']} entry(ies) — " +
                  ", ".join(f"{Path(r['source_path']).name}:{r['status']}" for r in result["restored"]))

    def _journal(self) -> None:
        entries = read_journal()
        self._fill([{"file": e.get("target_path") or e.get("source_path", ""), "finding": e.get("action", ""),
                     "detail": e.get("source_path", ""), "score": e.get("when", "")} for e in entries])
        self._say(f"{len(entries)} journal entries today.")

    def _export(self) -> None:
        if not self._rows:
            QMessageBox.information(self, "Nothing to export", "Run a scan first.")
            return
        default = str(RUNS / f"operations_export_{datetime.now():%Y%m%d_%H%M%S}.json")
        chosen, _ = QFileDialog.getSaveFileName(self, "Export", default, "JSON (*.json);;CSV (*.csv)")
        if not chosen:
            return
        out = Path(chosen)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".csv":
            import csv
            with out.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["file", "finding", "detail", "score"])
                writer.writeheader()
                writer.writerows(self._rows)
        else:
            out.write_text(json.dumps({"root": str(self._root()), "rows": self._rows,
                                       "report": self._last_report}, indent=2, default=str), encoding="utf-8")
        self._say(f"Exported {len(self._rows)} rows → {out}")


def main() -> int:
    app = QApplication(sys.argv)
    window = OperationsPanel()
    window.setWindowTitle("David-OS v3 — Operations")
    window.resize(1200, 860)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
