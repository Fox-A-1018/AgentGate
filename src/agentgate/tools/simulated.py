from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from agentgate.errors import ToolExecutionError
from agentgate.executor import ToolRegistry
from agentgate.models import ReasonCode


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _file_reader(sandbox_root: Path):
    resolved_root = sandbox_root.resolve()

    def read_file(parameters: dict[str, Any]) -> dict[str, Any]:
        relative = Path(*PurePosixPath(parameters["path"]).parts)
        candidate = (resolved_root / relative).resolve(strict=True)
        if not candidate.is_relative_to(resolved_root) or not candidate.is_file():
            raise ToolExecutionError(ReasonCode.RESOURCE_OUT_OF_SCOPE, "file is outside the sandbox")
        content = candidate.read_text(encoding="utf-8")
        return {
            "path": parameters["path"],
            "content": content,
            "bytes": len(content.encode("utf-8")),
        }

    return read_file


def _database_reader(database_path: Path):
    def select_rows(parameters: dict[str, Any]) -> dict[str, Any]:
        table = parameters["table"]
        fields = parameters["fields"]
        filters = parameters["filters"]
        if not IDENTIFIER.fullmatch(table) or any(not IDENTIFIER.fullmatch(field) for field in fields):
            raise ToolExecutionError(ReasonCode.PARAMETER_INVALID, "invalid database identifier")
        if any(not IDENTIFIER.fullmatch(field) for field in filters):
            raise ToolExecutionError(ReasonCode.PARAMETER_INVALID, "invalid filter identifier")
        field_sql = ", ".join(f'"{field}"' for field in fields)
        query = f'SELECT {field_sql} FROM "{table}"'
        values: list[Any] = []
        if filters:
            clauses = []
            for field, value in filters.items():
                clauses.append(f'"{field}" = ?')
                values.append(value)
            query += " WHERE " + " AND ".join(clauses)
        query += " LIMIT ?"
        values.append(parameters["limit"])
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(query, values).fetchall()]
        return {"table": table, "row_count": len(rows), "rows": rows}

    return select_rows


def _mail_writer(outbox_path: Path):
    outbox_path.parent.mkdir(parents=True, exist_ok=True)

    def write_mail(parameters: dict[str, Any]) -> dict[str, Any]:
        body = parameters["body"]
        record = {
            "message_id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "recipients": parameters["recipients"],
            "subject": parameters["subject"],
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "body_length": len(body),
        }
        with outbox_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        return {
            "message_id": record["message_id"],
            "recipients": record["recipients"],
            "outbox": str(outbox_path),
        }

    return write_mail


def build_default_registry(
    sandbox_root: str | Path,
    business_database_path: str | Path,
    outbox_path: str | Path,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("file.read", _file_reader(Path(sandbox_root)))
    registry.register("db.select", _database_reader(Path(business_database_path)))
    registry.register("mail.send", _mail_writer(Path(outbox_path)))
    return registry

