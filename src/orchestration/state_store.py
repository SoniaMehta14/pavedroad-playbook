"""SQLite-backed state store for orchestration runs.

Every agent step is a logged, replayable state transition — never held
only in memory. The lesson behind this is expensive: IBM API Connect's
original Cassandra layer, with a homegrown compensation scheme on top of
it, could not maintain transaction integrity, and engineers spent
multi-hour customer calls hand-fixing corrupted state. An orchestration
pipeline whose intermediate state cannot be audited or replayed will
eventually produce a result nobody can explain — this store exists so
that never happens here.

Schema is designed to port to PostgreSQL without surprises: explicit
column types, no SQLite-specific dynamic-typing tricks, JSON blobs stored
as plain TEXT (both engines support this identically via a
JSON-serialized string column).
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

RunStatus = Literal["running", "halted", "completed", "failed"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    token_budget INTEGER NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    resume_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    task_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    agent_name TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    thought_process TEXT NOT NULL,
    model_used TEXT,
    model_tier TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunRecord:
    run_id: str
    workflow_name: str
    status: RunStatus
    token_budget: int
    tokens_used: int
    cost_usd: float
    resume_index: int


@dataclass
class StateTransition:
    id: int
    run_id: str
    task_id: str
    step_index: int
    agent_name: str
    from_state: str
    to_state: str
    thought_process: dict[str, Any]
    model_used: str | None
    model_tier: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: str


class StateStore:
    """A single-connection wrapper around the SQLite execution log.

    Not thread-safe by design — this reference implementation runs one
    pipeline at a time. A production port to PostgreSQL would add
    connection pooling here; the schema itself needs no changes.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def start_run(self, run_id: str, workflow_name: str, *, token_budget: int) -> None:
        now = _now()
        self._conn.execute(
            "INSERT INTO runs "
            "(run_id, workflow_name, status, token_budget, created_at, updated_at) "
            "VALUES (?, ?, 'running', ?, ?, ?)",
            (run_id, workflow_name, token_budget, now, now),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> RunRecord:
        row = self._conn.execute(
            "SELECT run_id, workflow_name, status, token_budget, tokens_used, cost_usd, "
            "resume_index FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"no run with id {run_id!r}")
        return RunRecord(*row)

    def record_usage(
        self, run_id: str, *, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        self._conn.execute(
            "UPDATE runs SET tokens_used = tokens_used + ?, cost_usd = cost_usd + ?, "
            "updated_at = ? WHERE run_id = ?",
            (input_tokens + output_tokens, cost_usd, _now(), run_id),
        )
        self._conn.commit()

    def log_transition(
        self,
        *,
        run_id: str,
        task_id: str,
        step_index: int,
        agent_name: str,
        from_state: str,
        to_state: str,
        thought_process: dict[str, Any],
        model_used: str | None = None,
        model_tier: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        self._conn.execute(
            "INSERT INTO state_transitions "
            "(run_id, task_id, step_index, agent_name, from_state, to_state, thought_process, "
            "model_used, model_tier, input_tokens, output_tokens, cost_usd, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                task_id,
                step_index,
                agent_name,
                from_state,
                to_state,
                json.dumps(thought_process),
                model_used,
                model_tier,
                input_tokens,
                output_tokens,
                cost_usd,
                _now(),
            ),
        )
        self._conn.commit()

    def transitions_for_run(self, run_id: str) -> list[StateTransition]:
        rows = self._conn.execute(
            "SELECT id, run_id, task_id, step_index, agent_name, from_state, to_state, "
            "thought_process, model_used, model_tier, input_tokens, output_tokens, cost_usd, "
            "created_at FROM state_transitions WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        return [
            StateTransition(
                id=r[0],
                run_id=r[1],
                task_id=r[2],
                step_index=r[3],
                agent_name=r[4],
                from_state=r[5],
                to_state=r[6],
                thought_process=json.loads(r[7]),
                model_used=r[8],
                model_tier=r[9],
                input_tokens=r[10],
                output_tokens=r[11],
                cost_usd=r[12],
                created_at=r[13],
            )
            for r in rows
        ]

    def halt_run(self, run_id: str, *, resume_index: int) -> None:
        self._conn.execute(
            "UPDATE runs SET status = 'halted', resume_index = ?, updated_at = ? WHERE run_id = ?",
            (resume_index, _now(), run_id),
        )
        self._conn.commit()

    def complete_run(self, run_id: str) -> None:
        self._conn.execute(
            "UPDATE runs SET status = 'completed', updated_at = ? WHERE run_id = ?",
            (_now(), run_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
