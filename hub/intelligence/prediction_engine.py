"""Interpretable file-action prediction engine.

This engine is deliberately simple: no ML libraries, no opaque model, and no
hidden automation. It predicts likely file actions from observed behavior using
five explainable signals:

1. destination frequency with recency decay,
2. naming pattern reuse,
3. temporal context,
4. source-folder affinity,
5. co-occurrence of file types.

It is meant to feed the review gate, not bypass it.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import math
import os
import re
import sqlite3
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Prediction:
    id: str
    action: str
    file_path: str
    destination: str | None
    rename_suggestion: str | None
    confidence: float
    reasons: list[tuple[str, float, str]]
    alternatives: list[dict[str, Any]]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "file_path": self.file_path,
            "destination": self.destination,
            "rename_suggestion": self.rename_suggestion,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "alternatives": self.alternatives[:3],
            "timestamp": self.timestamp,
        }


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    return str(Path(path)).replace("\\", "/").rstrip("/").lower()


def _folder_of(path: str | None) -> str | None:
    if not path:
        return None
    return str(Path(path).parent)


def _recency_weight(timestamp: str, halflife_days: float = 30.0) -> float:
    try:
        observed_at = dt.datetime.fromisoformat(timestamp)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=dt.timezone.utc)
        age_days = (dt.datetime.now(dt.timezone.utc) - observed_at).total_seconds() / 86400
        return math.exp(-math.log(2) * age_days / halflife_days)
    except (TypeError, ValueError):
        return 0.5


def _extract_name_pattern(names: list[str]) -> dict[str, Any]:
    patterns: dict[str, Any] = {
        "uses_dates": 0,
        "uses_underscores": 0,
        "uses_hyphens": 0,
        "uses_camel_case": 0,
        "date_format": Counter(),
        "prefix": Counter(),
    }
    date_patterns = [
        (r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD"),
        (r"\d{4}_\d{2}_\d{2}", "YYYY_MM_DD"),
        (r"\d{8}", "YYYYMMDD"),
        (r"\d{2}-\d{2}-\d{4}", "MM-DD-YYYY"),
    ]

    for name in names:
        stem = Path(name).stem
        patterns["uses_underscores"] += int("_" in stem)
        patterns["uses_hyphens"] += int("-" in stem)
        patterns["uses_camel_case"] += int(bool(re.search(r"[a-z][A-Z]", stem)))
        for pattern, label in date_patterns:
            if re.search(pattern, stem):
                patterns["uses_dates"] += 1
                patterns["date_format"][label] += 1
                break
        prefix = re.split(r"[_\-\s]", stem)[0].lower()
        if len(prefix) > 1:
            patterns["prefix"][prefix] += 1
    return patterns


def _format_today(date_format: str, separator: str) -> str:
    now = dt.datetime.now()
    if date_format == "YYYYMMDD":
        return now.strftime("%Y%m%d")
    if date_format == "YYYY-MM-DD":
        return now.strftime("%Y-%m-%d")
    if date_format == "YYYY_MM_DD":
        return now.strftime("%Y_%m_%d")
    return now.strftime(f"%Y{separator}%m{separator}%d")


def _suggest_name(file_name: str, patterns: dict[str, Any], extension: str) -> str:
    stem = Path(file_name).stem
    separator = "-" if patterns.get("uses_hyphens", 0) > patterns.get("uses_underscores", 0) else "_"
    cleaned = re.sub(r"^(IMG_|DSC_|Screenshot[_ ]|VID_|MOV_|Photo_)", "", stem, flags=re.I)
    cleaned = re.sub(r"[_\-\s]+", separator, cleaned).strip(separator).lower()

    date_votes: Counter = patterns.get("date_format", Counter())
    sample_count = sum(patterns.get(key, 0) for key in ("uses_underscores", "uses_hyphens")) or 1
    if patterns.get("uses_dates", 0) / sample_count >= 0.3:
        date_label = date_votes.most_common(1)[0][0] if date_votes else "YYYY_MM_DD"
        today = _format_today(date_label, separator)
        if today not in cleaned:
            cleaned = f"{today}{separator}{cleaned}" if cleaned else today

    return f"{cleaned or stem.lower()}{extension}"


class PredictionDB:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                extension TEXT NOT NULL,
                source_folder TEXT NOT NULL,
                destination TEXT,
                dest_folder TEXT,
                old_name TEXT,
                new_name TEXT,
                hour INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                chi_dominant TEXT NOT NULL DEFAULT '',
                chi_hash TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                action TEXT NOT NULL,
                predicted_dest TEXT,
                predicted_name TEXT,
                confidence REAL NOT NULL,
                actual_dest TEXT,
                actual_name TEXT,
                was_correct INTEGER,
                was_overridden INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS permanent_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type TEXT NOT NULL,
                pattern TEXT NOT NULL,
                action TEXT NOT NULL,
                destination TEXT,
                name_template TEXT,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_from_prediction TEXT,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_observations_ext ON observations(extension);
            CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_folder);
            CREATE INDEX IF NOT EXISTS idx_observations_time ON observations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_predictions_resolved ON predictions(resolved_at);
            CREATE INDEX IF NOT EXISTS idx_rules_action ON permanent_rules(action, active);
            """
        )
        self.conn.commit()

    def record_observation(
        self,
        *,
        action: str,
        file_path: str,
        destination: str | None = None,
        old_name: str | None = None,
        new_name: str | None = None,
        timestamp: dt.datetime | None = None,
        chi_dominant: str = "",
        chi_hash: str = "",
    ) -> None:
        timestamp = timestamp or dt.datetime.now(dt.timezone.utc)
        path = Path(file_path)
        self.conn.execute(
            """
            INSERT INTO observations (
                action, file_path, file_name, extension, source_folder,
                destination, dest_folder, old_name, new_name, hour, day_of_week,
                chi_dominant, chi_hash, timestamp, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action,
                str(file_path),
                path.name,
                path.suffix.lower(),
                str(path.parent),
                destination,
                _folder_of(destination),
                old_name,
                new_name,
                timestamp.hour,
                timestamp.weekday(),
                chi_dominant,
                chi_hash,
                timestamp.isoformat(),
                _utc_now(),
            ),
        )
        self.conn.commit()

    def observations(self, *, extension: str | None = None, limit: int = 500) -> list[sqlite3.Row]:
        if extension:
            return self.conn.execute(
                "SELECT * FROM observations WHERE extension = ? ORDER BY timestamp DESC LIMIT ?",
                (extension, limit),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM observations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def total_observations(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) AS c FROM observations").fetchone()["c"])

    def record_prediction(self, prediction: Prediction) -> None:
        self.conn.execute(
            """
            INSERT INTO predictions (
                id, file_path, action, predicted_dest, predicted_name, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction.id,
                prediction.file_path,
                prediction.action,
                prediction.destination,
                prediction.rename_suggestion,
                prediction.confidence,
                prediction.timestamp,
            ),
        )
        self.conn.commit()

    def resolve_prediction(
        self,
        prediction_id: str,
        *,
        actual_destination: str | None = None,
        actual_name: str | None = None,
    ) -> None:
        row = self.conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
        if not row:
            return
        correct = True
        if actual_destination and row["predicted_dest"]:
            correct = correct and _normalize_path(actual_destination) == _normalize_path(row["predicted_dest"])
        if actual_name and row["predicted_name"]:
            correct = correct and actual_name.lower() == row["predicted_name"].lower()
        self.conn.execute(
            """
            UPDATE predictions
            SET actual_dest = ?, actual_name = ?, was_correct = ?, was_overridden = ?, resolved_at = ?
            WHERE id = ?
            """,
            (actual_destination, actual_name, int(correct), int(not correct), _utc_now(), prediction_id),
        )
        self.conn.commit()

    def accuracy(self, last_n: int = 100) -> dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT was_correct
            FROM predictions
            WHERE was_correct IS NOT NULL
            ORDER BY resolved_at DESC
            LIMIT ?
            """,
            (last_n,),
        ).fetchall()
        total = len(rows)
        correct = sum(1 for row in rows if row["was_correct"])
        return {
            "total_predictions": total,
            "correct": correct,
            "accuracy": correct / total if total else 0.0,
        }

    def add_rule(
        self,
        *,
        rule_type: str,
        pattern: str,
        action: str,
        destination: str | None,
        name_template: str | None,
        from_prediction: str | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO permanent_rules (
                rule_type, pattern, action, destination, name_template,
                created_from_prediction, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (rule_type, pattern, action, destination, name_template, from_prediction, _utc_now()),
        )
        self.conn.commit()

    def rules(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        where = "WHERE active = 1" if active_only else ""
        return [dict(row) for row in self.conn.execute(f"SELECT * FROM permanent_rules {where} ORDER BY hit_count DESC")]

    def increment_rule_hit(self, rule_id: int) -> None:
        self.conn.execute("UPDATE permanent_rules SET hit_count = hit_count + 1 WHERE id = ?", (rule_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


class PredictionEngine:
    SIGNAL_WEIGHTS = {
        "destination_frequency": 0.35,
        "naming_pattern": 0.25,
        "temporal_context": 0.15,
        "folder_affinity": 0.15,
        "cooccurrence": 0.10,
    }

    def __init__(self, data_dir: str | Path = ".data/predictions") -> None:
        self.data_dir = Path(data_dir)
        self.db = PredictionDB(self.data_dir / "predictions.sqlite3")

    def close(self) -> None:
        self.db.close()

    def observe(
        self,
        *,
        action: str,
        file_path: str,
        destination: str | None = None,
        old_name: str | None = None,
        new_name: str | None = None,
        timestamp: dt.datetime | None = None,
        chi_dominant: str = "",
        chi_hash: str = "",
    ) -> None:
        self.db.record_observation(
            action=action,
            file_path=file_path,
            destination=destination,
            old_name=old_name,
            new_name=new_name,
            timestamp=timestamp,
            chi_dominant=chi_dominant,
            chi_hash=chi_hash,
        )

    def predict(self, *, file_path: str, action: str = "move") -> Prediction:
        path = Path(file_path)
        extension = path.suffix.lower()
        rule = self._matching_rule(file_path, action)
        if rule:
            prediction = Prediction(
                id=str(uuid.uuid4())[:12],
                action=action,
                file_path=file_path,
                destination=rule.get("destination"),
                rename_suggestion=rule.get("name_template"),
                confidence=1.0,
                reasons=[("permanent_rule", 1.0, f"Matched {rule['pattern']}")],
                alternatives=[],
                timestamp=_utc_now(),
            )
            self.db.record_prediction(prediction)
            self.db.increment_rule_hit(int(rule["id"]))
            return prediction

        signal_outputs = {
            "destination_frequency": self._signal_destination_frequency(extension),
            "naming_pattern": self._signal_naming_pattern(path.name, extension),
            "temporal_context": self._signal_temporal_context(extension),
            "folder_affinity": self._signal_folder_affinity(extension, str(path.parent)),
            "cooccurrence": self._signal_cooccurrence(extension),
        }

        destination_votes: defaultdict[str, float] = defaultdict(float)
        reasons: list[tuple[str, float, str]] = []
        rename_suggestion: str | None = None
        for signal, (score, value, explanation) in signal_outputs.items():
            weighted = score * self.SIGNAL_WEIGHTS[signal]
            reasons.append((signal, round(weighted, 3), explanation))
            if signal == "naming_pattern":
                rename_suggestion = value
            elif value:
                destination_votes[_normalize_path(value) or value] += weighted

        sorted_dests = sorted(destination_votes.items(), key=lambda item: item[1], reverse=True)
        best_dest = sorted_dests[0][0] if sorted_dests else None
        best_score = sorted_dests[0][1] if sorted_dests else 0.0
        obs_factor = min(1.0, self.db.total_observations() / 100)
        confidence = min(0.99, best_score * obs_factor)
        prediction = Prediction(
            id=str(uuid.uuid4())[:12],
            action=action,
            file_path=file_path,
            destination=best_dest,
            rename_suggestion=rename_suggestion,
            confidence=confidence,
            reasons=reasons,
            alternatives=[{"destination": dest, "score": round(score, 3)} for dest, score in sorted_dests[1:4]],
            timestamp=_utc_now(),
        )
        self.db.record_prediction(prediction)
        return prediction

    def correct(self, prediction_id: str, *, actual_destination: str | None = None, actual_name: str | None = None) -> None:
        self.db.resolve_prediction(prediction_id, actual_destination=actual_destination, actual_name=actual_name)

    def make_permanent(self, prediction_id: str, *, rule_type: str = "extension", pattern: str | None = None) -> dict[str, Any] | None:
        row = self.db.conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
        if not row:
            return None
        pattern = pattern or f"*{Path(row['file_path']).suffix.lower()}"
        self.db.add_rule(
            rule_type=rule_type,
            pattern=pattern,
            action=row["action"],
            destination=row["predicted_dest"],
            name_template=row["predicted_name"],
            from_prediction=prediction_id,
        )
        return {"status": "rule_created", "pattern": pattern}

    def stats(self) -> dict[str, Any]:
        accuracy = self.db.accuracy()
        observations = self.db.total_observations()
        if observations < 20:
            trust_name = "Silent Observer"
            trust_level = 0
        elif accuracy["accuracy"] < 0.60:
            trust_name = "Prediction Only"
            trust_level = 1
        elif accuracy["accuracy"] < 0.80:
            trust_name = "Suggestion + Confirm"
            trust_level = 2
        elif accuracy["accuracy"] < 0.95:
            trust_name = "Auto + Log"
            trust_level = 3
        else:
            trust_name = "Full Partner"
            trust_level = 4
        return {
            "total_observations": observations,
            "prediction_accuracy": accuracy,
            "permanent_rules": len(self.db.rules()),
            "trust_level": trust_level,
            "trust_name": trust_name,
            "ready_to_predict": observations >= 20,
            "signals": self.SIGNAL_WEIGHTS,
        }

    def _signal_destination_frequency(self, extension: str) -> tuple[float, str | None, str]:
        observations = self.db.observations(extension=extension, limit=100)
        scores: defaultdict[str, float] = defaultdict(float)
        for row in observations:
            if row["dest_folder"] and row["action"] in {"move", "archive"}:
                scores[row["dest_folder"]] += _recency_weight(row["timestamp"])
        if not scores:
            return 0.0, None, f"No move history for {extension or 'extensionless'} files"
        destination, score = max(scores.items(), key=lambda item: item[1])
        total = sum(scores.values()) or 1.0
        confidence = score / total
        return confidence, destination, f"{extension} files most often go to {Path(destination).name}/ ({confidence:.0%} weighted)"

    def _signal_naming_pattern(self, file_name: str, extension: str) -> tuple[float, str | None, str]:
        observations = self.db.observations(extension=extension, limit=100)
        names = [row["new_name"] for row in observations if row["action"] == "rename" and row["new_name"]]
        if len(names) < 3:
            names = [row["file_name"] for row in observations if row["file_name"]]
        if len(names) < 5:
            return 0.0, None, "Not enough naming history"
        patterns = _extract_name_pattern(names)
        score = min(1.0, len(names) / 20)
        return score, _suggest_name(file_name, patterns, extension), f"Based on {len(names)} observed {extension} names"

    def _signal_temporal_context(self, extension: str) -> tuple[float, str | None, str]:
        now = dt.datetime.now()
        observations = self.db.observations(extension=extension, limit=200)
        scores: defaultdict[str, float] = defaultdict(float)
        for row in observations:
            if not row["dest_folder"]:
                continue
            if abs((row["hour"] or 12) - now.hour) <= 2:
                scores[row["dest_folder"]] += _recency_weight(row["timestamp"])
        if not scores:
            return 0.0, None, "No same-time history"
        destination, score = max(scores.items(), key=lambda item: item[1])
        confidence = 0.7 * (score / (sum(scores.values()) or 1.0))
        return confidence, destination, f"At this time, similar files often go to {Path(destination).name}/"

    def _signal_folder_affinity(self, extension: str, source_folder: str) -> tuple[float, str | None, str]:
        source_norm = _normalize_path(source_folder)
        observations = self.db.observations(extension=extension, limit=200)
        scores: defaultdict[str, float] = defaultdict(float)
        for row in observations:
            obs_source = _normalize_path(row["source_folder"])
            if obs_source and row["dest_folder"] and (obs_source == source_norm or source_norm.startswith(obs_source)):
                scores[row["dest_folder"]] += _recency_weight(row["timestamp"])
        if not scores:
            return 0.0, None, f"No source-folder history for {Path(source_folder).name}/"
        destination, score = max(scores.items(), key=lambda item: item[1])
        confidence = score / (sum(scores.values()) or 1.0)
        return confidence, destination, f"Files from {Path(source_folder).name}/ often go to {Path(destination).name}/"

    def _signal_cooccurrence(self, extension: str) -> tuple[float, str | None, str]:
        observations = [dict(row) for row in self.db.observations(limit=500)]
        if len(observations) < 20:
            return 0.0, None, "Not enough co-occurrence data"
        sorted_rows = sorted(observations, key=lambda row: row["timestamp"])
        pairs: defaultdict[str, Counter[str]] = defaultdict(Counter)
        for current, nxt in zip(sorted_rows, sorted_rows[1:]):
            try:
                current_ts = dt.datetime.fromisoformat(current["timestamp"])
                next_ts = dt.datetime.fromisoformat(nxt["timestamp"])
            except (TypeError, ValueError):
                continue
            if abs((next_ts - current_ts).total_seconds()) < 60:
                a, b = current["extension"], nxt["extension"]
                if a and b and a != b:
                    pairs[a][b] += 1
                    pairs[b][a] += 1
        if extension not in pairs or not pairs[extension]:
            return 0.0, None, f"No co-occurrence partners for {extension}"
        partner, count = pairs[extension].most_common(1)[0]
        if count < 3:
            return 0.0, None, f"Weak co-occurrence signal ({count} instances)"
        destinations = Counter(row["dest_folder"] for row in observations if row["extension"] == partner and row["dest_folder"])
        if not destinations:
            return 0.0, None, "Co-occurrence found without destination history"
        destination = destinations.most_common(1)[0][0]
        return min(1.0, count / 10), destination, f"{extension} often moves with {partner}, which goes to {Path(destination).name}/"

    def _matching_rule(self, file_path: str, action: str) -> dict[str, Any] | None:
        for rule in self.db.rules(active_only=True):
            if rule["action"] == action and fnmatch.fnmatch(file_path.lower(), rule["pattern"].lower()):
                return rule
        return None


def default_prediction_engine() -> PredictionEngine:
    data_dir = os.environ.get("FIHUB_PREDICTION_DIR", ".data/predictions")
    return PredictionEngine(data_dir)
