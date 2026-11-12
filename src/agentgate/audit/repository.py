from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agentgate.models import AuditEvent


class AuditRepository:
    """Append-only SQLite audit event repository."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    parent_event_id TEXT,
                    subject_id TEXT,
                    role TEXT,
                    tool_name TEXT,
                    decision TEXT,
                    reason_code TEXT,
                    risk_level TEXT,
                    parameter_hash TEXT,
                    policy_version TEXT,
                    approval_id TEXT,
                    execution_status TEXT,
                    details_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id, sequence)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id, sequence)"
            )

    def record(self, event: AuditEvent) -> None:
        data = event.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, event_type, trace_id, request_id, occurred_at,
                    parent_event_id, subject_id, role, tool_name, decision,
                    reason_code, risk_level, parameter_hash, policy_version,
                    approval_id, execution_status, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["event_id"],
                    data["event_type"],
                    data["trace_id"],
                    data["request_id"],
                    data["occurred_at"],
                    data["parent_event_id"],
                    data["subject_id"],
                    data["role"],
                    data["tool_name"],
                    data["decision"],
                    data["reason_code"],
                    data["risk_level"],
                    data["parameter_hash"],
                    data["policy_version"],
                    data["approval_id"],
                    data["execution_status"],
                    json.dumps(data["details"], ensure_ascii=True, sort_keys=True),
                ),
            )

    def list_trace(self, trace_id: str) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE trace_id = ? ORDER BY sequence",
                (trace_id,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_request(self, request_id: str) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE request_id = ? ORDER BY sequence",
                (request_id,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_recent(self, limit: int = 100) -> list[AuditEvent]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY sequence DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> AuditEvent:
        return AuditEvent.model_validate(
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "trace_id": row["trace_id"],
                "request_id": row["request_id"],
                "occurred_at": row["occurred_at"],
                "parent_event_id": row["parent_event_id"],
                "subject_id": row["subject_id"],
                "role": row["role"],
                "tool_name": row["tool_name"],
                "decision": row["decision"],
                "reason_code": row["reason_code"],
                "risk_level": row["risk_level"],
                "parameter_hash": row["parameter_hash"],
                "policy_version": row["policy_version"],
                "approval_id": row["approval_id"],
                "execution_status": row["execution_status"],
                "details": json.loads(row["details_json"]),
            }
        )

