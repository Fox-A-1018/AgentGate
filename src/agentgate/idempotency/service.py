from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from agentgate.errors import IdempotencyError
from agentgate.models import GatewayResponse, NormalizedToolCall, ReasonCode


class IdempotencyService:
    """Persistent reservation and replay store for idempotent gateway submissions."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    subject_id TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (subject_id, key_hash)
                )
                """
            )

    def begin(self, call: NormalizedToolCall) -> GatewayResponse | None:
        if call.idempotency_key is None:
            return None
        key_hash = self._key_hash(call.idempotency_key)
        fingerprint = self._fingerprint(call)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT request_fingerprint, response_json
                FROM idempotency_records
                WHERE subject_id = ? AND key_hash = ?
                """,
                (call.subject_id, key_hash),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO idempotency_records (
                        subject_id, key_hash, request_fingerprint,
                        response_json, created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, ?, ?)
                    """,
                    (call.subject_id, key_hash, fingerprint, now, now),
                )
                connection.commit()
                return None
            if row["request_fingerprint"] != fingerprint:
                connection.rollback()
                raise IdempotencyError(
                    ReasonCode.IDEMPOTENCY_CONFLICT,
                    "idempotency key was already used for a different request",
                )
            if row["response_json"] is None:
                connection.rollback()
                raise IdempotencyError(
                    ReasonCode.IDEMPOTENCY_IN_PROGRESS,
                    "an equivalent request with this idempotency key is still in progress",
                )
            connection.commit()
        return GatewayResponse.model_validate_json(row["response_json"])

    def complete(self, call: NormalizedToolCall, response: GatewayResponse) -> None:
        if call.idempotency_key is None:
            return
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE idempotency_records
                SET response_json = ?, updated_at = ?
                WHERE subject_id = ? AND key_hash = ? AND request_fingerprint = ?
                """,
                (
                    response.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                    call.subject_id,
                    self._key_hash(call.idempotency_key),
                    self._fingerprint(call),
                ),
            )

    @staticmethod
    def key_digest(call: NormalizedToolCall) -> str | None:
        if call.idempotency_key is None:
            return None
        return IdempotencyService._key_hash(call.idempotency_key)

    @staticmethod
    def _key_hash(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint(call: NormalizedToolCall) -> str:
        canonical = {
            "subject_id": call.subject_id,
            "role": call.role.value,
            "tool_name": call.tool_name,
            "parameters": call.parameters,
            "policy_version": call.policy_version,
        }
        payload = json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
