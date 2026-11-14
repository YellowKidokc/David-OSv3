"""Rule Brick: one advisory evidence surface for every David-OS worker.

Rule Brick records what an agent intends to do, the predictions it makes, the
evidence behind them, and what actually happened.  It never authorizes or
performs filesystem mutation.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class Signal:
    name: str
    direction: int
    weight: float
    reliability: float
    evidence: str

    def __post_init__(self) -> None:
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")
        if not 0 <= self.weight:
            raise ValueError("weight must be non-negative")
        if not 0 <= self.reliability <= 1:
            raise ValueError("reliability must be between 0 and 1")


def score_signals(signals: Iterable[Signal], *, evidence_target: float = 5.0) -> dict[str, float]:
    """Combine evidence without pretending correlated signals are independent.

    The raw balance is shrunk toward 0.5 when evidence coverage is sparse.  It
    is an interpretable ranking score, not a calibrated probability until
    historical outcomes establish calibration.
    """
    rows = list(signals)
    mass = sum(row.weight * row.reliability for row in rows)
    if mass == 0:
        return {"score": 0.5, "coverage": 0.0, "support": 0.0, "opposition": 0.0}
    support = sum(row.weight * row.reliability for row in rows if row.direction > 0)
    opposition = mass - support
    raw = support / mass
    coverage = min(1.0, mass / max(evidence_target, 0.001))
    score = 0.5 + (raw - 0.5) * coverage
    return {
        "score": round(score, 6),
        "coverage": round(coverage, 6),
        "support": round(support, 6),
        "opposition": round(opposition, 6),
    }


class RuleBrick:
    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "rule_brick.sqlite"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    @staticmethod
    def questions() -> list[dict[str, object]]:
        path = Path(__file__).with_name("questions.json")
        return json.loads(path.read_text(encoding="utf-8"))["questions"]

    @staticmethod
    def principles() -> str:
        return Path(__file__).with_name("PRINCIPLES.md").read_text(encoding="utf-8")

    def _init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS work_sessions (
              session_id TEXT PRIMARY KEY,
              agent_id TEXT NOT NULL,
              intent TEXT NOT NULL,
              roots_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'open',
              started_at TEXT NOT NULL,
              completed_at TEXT,
              outcome TEXT
            );
            CREATE TABLE IF NOT EXISTS predictions (
              prediction_id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL REFERENCES work_sessions(session_id),
              question_id TEXT NOT NULL,
              subject_path TEXT NOT NULL,
              engine TEXT NOT NULL,
              score REAL NOT NULL CHECK(score BETWEEN 0 AND 1),
              coverage REAL NOT NULL CHECK(coverage BETWEEN 0 AND 1),
              evidence_json TEXT NOT NULL,
              counterevidence_json TEXT NOT NULL,
              unknowns_json TEXT NOT NULL,
              recommendation TEXT,
              created_at TEXT NOT NULL,
              actual_outcome TEXT,
              resolved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS work_events (
              event_id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL REFERENCES work_sessions(session_id),
              phase TEXT NOT NULL CHECK(phase IN ('before','during','after')),
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def before_work(self, *, agent_id: str, intent: str, roots: Sequence[str]) -> dict[str, object]:
        session_id = str(uuid.uuid4())
        now = _now()
        self.conn.execute(
            "INSERT INTO work_sessions(session_id,agent_id,intent,roots_json,started_at) VALUES(?,?,?,?,?)",
            (session_id, agent_id, intent, json.dumps(list(roots)), now),
        )
        self._event(session_id, "before", "intent_registered", {"intent": intent, "roots": list(roots)})
        self.conn.commit()
        return {
            "session_id": session_id,
            "authority": "advisory_only",
            "principles": self.principles(),
            "questions": self.questions(),
        }

    def record_prediction(
        self,
        *,
        session_id: str,
        question_id: str,
        subject_path: str,
        engine: str,
        signals: Sequence[Signal],
        counterevidence: Sequence[str] = (),
        unknowns: Sequence[str] = (),
        recommendation: str | None = None,
    ) -> dict[str, object]:
        known = {str(row["id"]) for row in self.questions()}
        if question_id not in known:
            raise ValueError(f"unknown Rule Brick question: {question_id}")
        self._require_open(session_id)
        result = score_signals(signals)
        prediction_id = str(uuid.uuid4())
        evidence = [asdict(row) for row in signals]
        self.conn.execute(
            """INSERT INTO predictions(
                 prediction_id,session_id,question_id,subject_path,engine,score,coverage,
                 evidence_json,counterevidence_json,unknowns_json,recommendation,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                prediction_id, session_id, question_id, subject_path, engine,
                result["score"], result["coverage"], json.dumps(evidence),
                json.dumps(list(counterevidence)), json.dumps(list(unknowns)),
                recommendation, _now(),
            ),
        )
        self._event(session_id, "during", "prediction_recorded", {"prediction_id": prediction_id})
        self.conn.commit()
        return {"prediction_id": prediction_id, **result, "authority": "advisory_only"}

    def resolve_prediction(self, prediction_id: str, actual_outcome: str) -> None:
        self.conn.execute(
            "UPDATE predictions SET actual_outcome=?, resolved_at=? WHERE prediction_id=?",
            (actual_outcome, _now(), prediction_id),
        )
        self.conn.commit()

    def after_work(self, *, session_id: str, status: str, outcome: str) -> dict[str, object]:
        self._require_open(session_id)
        now = _now()
        self.conn.execute(
            "UPDATE work_sessions SET status=?, completed_at=?, outcome=? WHERE session_id=?",
            (status, now, outcome, session_id),
        )
        self._event(session_id, "after", "work_closed", {"status": status, "outcome": outcome})
        self.conn.commit()
        count = self.conn.execute(
            "SELECT COUNT(*) AS count FROM predictions WHERE session_id=?", (session_id,)
        ).fetchone()["count"]
        return {"session_id": session_id, "status": status, "prediction_count": count, "outcome": outcome}

    def _event(self, session_id: str, phase: str, event_type: str, payload: dict[str, object]) -> None:
        self.conn.execute(
            "INSERT INTO work_events VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, phase, event_type, json.dumps(payload), _now()),
        )

    def _require_open(self, session_id: str) -> None:
        row = self.conn.execute(
            "SELECT status FROM work_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown work session: {session_id}")
        if row["status"] != "open":
            raise ValueError(f"work session is not open: {session_id}")

    def close(self) -> None:
        self.conn.close()
