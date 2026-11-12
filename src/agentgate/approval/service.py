from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentgate.errors import ApprovalError
from agentgate.models import (
    ApprovalGrant,
    ApprovalRecord,
    ApprovalStatus,
    NormalizedToolCall,
    ReasonCode,
    Role,
    new_id,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalService:
    def __init__(
        self,
        database_path: str | Path,
        pending_ttl: timedelta = timedelta(minutes=30),
        grant_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.pending_ttl = pending_ttl
        self.grant_ttl = grant_ttl
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approver_id TEXT,
                    decision_reason TEXT,
                    token_hash TEXT,
                    used_at TEXT
                )
                """
            )

    def create(self, call: NormalizedToolCall) -> ApprovalRecord:
        now = _now()
        record = ApprovalRecord(
            approval_id=new_id(),
            trace_id=call.trace_id,
            request_id=call.request_id,
            subject_id=call.subject_id,
            role=call.role,
            tool_name=call.tool_name,
            request_hash=call.request_hash,
            policy_version=call.policy_version,
            parameters=call.parameters,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + self.pending_ttl,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals (
                    approval_id, trace_id, request_id, subject_id, role, tool_name,
                    request_hash, policy_version, parameters_json, status,
                    created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.approval_id,
                    record.trace_id,
                    record.request_id,
                    record.subject_id,
                    record.role.value,
                    record.tool_name,
                    record.request_hash,
                    record.policy_version,
                    json.dumps(record.parameters, ensure_ascii=True, sort_keys=True),
                    record.status.value,
                    record.created_at.isoformat(),
                    record.expires_at.isoformat(),
                ),
            )
        return record

    def get(self, approval_id: str) -> ApprovalRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
        if row is None:
            raise ApprovalError(ReasonCode.APPROVAL_NOT_FOUND, "approval request was not found")
        return self._row_to_record(row)

    def approve(
        self,
        approval_id: str,
        approver_id: str,
        approver_role: Role,
        reason: str | None = None,
    ) -> ApprovalGrant:
        if approver_role is not Role.APPROVER:
            raise ApprovalError(ReasonCode.TOOL_NOT_ALLOWED, "only the approver role can approve")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = _now()
        expires_at = now + self.grant_ttl
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_NOT_FOUND, "approval request was not found")
            if row["subject_id"] == approver_id:
                connection.rollback()
                raise ApprovalError(
                    ReasonCode.SELF_APPROVAL_FORBIDDEN, "request owners cannot approve their own request"
                )
            if row["status"] != ApprovalStatus.PENDING.value:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_NOT_PENDING, "approval is not pending")
            if datetime.fromisoformat(row["expires_at"]) <= now:
                connection.execute(
                    "UPDATE approvals SET status = ? WHERE approval_id = ?",
                    (ApprovalStatus.EXPIRED.value, approval_id),
                )
                connection.commit()
                raise ApprovalError(ReasonCode.APPROVAL_EXPIRED, "approval request expired")
            connection.execute(
                """
                UPDATE approvals
                SET status = ?, approver_id = ?, decision_reason = ?,
                    token_hash = ?, expires_at = ?
                WHERE approval_id = ?
                """,
                (
                    ApprovalStatus.APPROVED.value,
                    approver_id,
                    reason,
                    token_hash,
                    expires_at.isoformat(),
                    approval_id,
                ),
            )
            connection.commit()
        return ApprovalGrant(approval_id=approval_id, token=token, expires_at=expires_at)

    def deny(
        self,
        approval_id: str,
        approver_id: str,
        approver_role: Role,
        reason: str | None = None,
    ) -> ApprovalRecord:
        if approver_role is not Role.APPROVER:
            raise ApprovalError(ReasonCode.TOOL_NOT_ALLOWED, "only the approver role can deny")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_NOT_FOUND, "approval request was not found")
            if row["status"] != ApprovalStatus.PENDING.value:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_NOT_PENDING, "approval is not pending")
            connection.execute(
                """
                UPDATE approvals
                SET status = ?, approver_id = ?, decision_reason = ?
                WHERE approval_id = ?
                """,
                (ApprovalStatus.DENIED.value, approver_id, reason, approval_id),
            )
            connection.commit()
        return self.get(approval_id)

    def consume(self, approval_id: str, token: str, call: NormalizedToolCall) -> ApprovalRecord:
        now = _now()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_NOT_FOUND, "approval request was not found")
            if row["used_at"] is not None or row["status"] in {
                ApprovalStatus.EXECUTING.value,
                ApprovalStatus.SUCCEEDED.value,
                ApprovalStatus.FAILED.value,
            }:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_ALREADY_USED, "approval token was already consumed")
            if row["status"] != ApprovalStatus.APPROVED.value:
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_NOT_PENDING, "approval is not executable")
            if datetime.fromisoformat(row["expires_at"]) <= now:
                connection.execute(
                    "UPDATE approvals SET status = ? WHERE approval_id = ?",
                    (ApprovalStatus.EXPIRED.value, approval_id),
                )
                connection.commit()
                raise ApprovalError(ReasonCode.APPROVAL_EXPIRED, "approval grant expired")
            if row["request_hash"] != call.request_hash:
                connection.rollback()
                raise ApprovalError(
                    ReasonCode.APPROVAL_HASH_MISMATCH,
                    "approved request does not match the request being executed",
                )
            if not secrets.compare_digest(row["token_hash"] or "", token_hash):
                connection.rollback()
                raise ApprovalError(ReasonCode.APPROVAL_TOKEN_INVALID, "approval token is invalid")
            connection.execute(
                "UPDATE approvals SET status = ?, used_at = ? WHERE approval_id = ?",
                (ApprovalStatus.EXECUTING.value, now.isoformat(), approval_id),
            )
            connection.commit()
        return self.get(approval_id)

    def mark_complete(self, approval_id: str, succeeded: bool) -> ApprovalRecord:
        status = ApprovalStatus.SUCCEEDED if succeeded else ApprovalStatus.FAILED
        with self._connect() as connection:
            connection.execute(
                "UPDATE approvals SET status = ? WHERE approval_id = ? AND status = ?",
                (status.value, approval_id, ApprovalStatus.EXECUTING.value),
            )
        return self.get(approval_id)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord.model_validate(
            {
                "approval_id": row["approval_id"],
                "trace_id": row["trace_id"],
                "request_id": row["request_id"],
                "subject_id": row["subject_id"],
                "role": row["role"],
                "tool_name": row["tool_name"],
                "request_hash": row["request_hash"],
                "policy_version": row["policy_version"],
                "parameters": json.loads(row["parameters_json"]),
                "status": row["status"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "approver_id": row["approver_id"],
                "decision_reason": row["decision_reason"],
                "used_at": row["used_at"],
            }
        )

