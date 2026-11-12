from __future__ import annotations

import hashlib
import json
import posixpath
import re
from collections.abc import Callable
from typing import Any

from agentgate.errors import NormalizationError
from agentgate.models import NormalizedToolCall, ReasonCode, ToolCallRequest


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def _require_exact_keys(parameters: dict[str, Any], expected: set[str]) -> None:
    unexpected = set(parameters) - expected
    missing = expected - set(parameters)
    if unexpected or missing:
        fragments = []
        if missing:
            fragments.append(f"missing keys: {sorted(missing)}")
        if unexpected:
            fragments.append(f"unexpected keys: {sorted(unexpected)}")
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "; ".join(fragments))


def _normalize_file_read(parameters: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(parameters, {"path"})
    path = parameters["path"]
    if not isinstance(path, str) or not path.strip() or len(path) > 512:
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "path must be a non-empty string")
    portable = path.strip().replace("\\", "/")
    if portable.startswith("/") or DRIVE_PREFIX.match(portable):
        raise NormalizationError(ReasonCode.RESOURCE_OUT_OF_SCOPE, "absolute paths are forbidden")
    if ".." in portable.split("/"):
        raise NormalizationError(ReasonCode.RESOURCE_OUT_OF_SCOPE, "parent path traversal is forbidden")
    normalized = posixpath.normpath(portable)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise NormalizationError(ReasonCode.RESOURCE_OUT_OF_SCOPE, "path escapes the sandbox")
    return {"path": normalized}


def _normalize_db_select(parameters: dict[str, Any]) -> dict[str, Any]:
    allowed = {"table", "fields", "limit", "filters"}
    unexpected = set(parameters) - allowed
    required = {"table", "fields", "limit"}
    missing = required - set(parameters)
    if unexpected or missing:
        fragments = []
        if missing:
            fragments.append(f"missing keys: {sorted(missing)}")
        if unexpected:
            fragments.append(f"unexpected keys: {sorted(unexpected)}")
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "; ".join(fragments))

    table = parameters["table"]
    fields = parameters["fields"]
    limit = parameters["limit"]
    filters = parameters.get("filters", {})
    if not isinstance(table, str) or not IDENTIFIER.fullmatch(table):
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "table must be a valid identifier")
    if not isinstance(fields, list) or not fields:
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "fields must be a non-empty list")
    if any(not isinstance(field, str) or not IDENTIFIER.fullmatch(field) for field in fields):
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "every field must be a valid identifier")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "limit must be a positive integer")
    if not isinstance(filters, dict):
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "filters must be an object")
    normalized_filters: dict[str, Any] = {}
    for key, value in filters.items():
        if not isinstance(key, str) or not IDENTIFIER.fullmatch(key):
            raise NormalizationError(ReasonCode.PARAMETER_INVALID, "filter names must be identifiers")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise NormalizationError(ReasonCode.PARAMETER_INVALID, "filter values must be JSON scalars")
        normalized_filters[key.lower()] = value
    normalized_fields = [field.lower() for field in fields]
    if len(set(normalized_fields)) != len(normalized_fields):
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "duplicate fields are forbidden")
    return {
        "table": table.lower(),
        "fields": normalized_fields,
        "limit": limit,
        "filters": dict(sorted(normalized_filters.items())),
    }


def _normalize_mail_send(parameters: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(parameters, {"recipients", "subject", "body"})
    recipients = parameters["recipients"]
    subject = parameters["subject"]
    body = parameters["body"]
    if not isinstance(recipients, list) or not 1 <= len(recipients) <= 10:
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "recipients must contain 1 to 10 addresses")
    normalized_recipients = []
    for address in recipients:
        if not isinstance(address, str) or address.count("@") != 1:
            raise NormalizationError(ReasonCode.PARAMETER_INVALID, "recipient address is invalid")
        local, domain = address.strip().lower().split("@", 1)
        if not local or not domain or "." not in domain:
            raise NormalizationError(ReasonCode.PARAMETER_INVALID, "recipient address is invalid")
        normalized_recipients.append(f"{local}@{domain}")
    if not isinstance(subject, str) or len(subject) > 200:
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "subject must be at most 200 characters")
    if not isinstance(body, str) or len(body) > 5000:
        raise NormalizationError(ReasonCode.PARAMETER_INVALID, "body must be at most 5000 characters")
    return {
        "recipients": sorted(set(normalized_recipients)),
        "subject": subject.strip(),
        "body": body,
    }


class NormalizerRegistry:
    def __init__(self) -> None:
        self._normalizers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "file.read": _normalize_file_read,
            "db.select": _normalize_db_select,
            "mail.send": _normalize_mail_send,
        }

    def normalize(self, request: ToolCallRequest, policy_version: str) -> NormalizedToolCall:
        normalizer = self._normalizers.get(request.tool_name)
        if normalizer is None:
            raise NormalizationError(ReasonCode.UNKNOWN_TOOL, f"unknown tool: {request.tool_name}")
        parameters = normalizer(request.parameters)
        canonical = {
            "subject_id": request.subject_id,
            "role": request.role.value,
            "tool_name": request.tool_name,
            "parameters": parameters,
            "request_id": request.request_id,
            "policy_version": policy_version,
        }
        payload = json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        request_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return NormalizedToolCall(
            subject_id=request.subject_id,
            role=request.role,
            tool_name=request.tool_name,
            parameters=parameters,
            session_id=request.session_id,
            idempotency_key=request.idempotency_key,
            trace_id=request.trace_id,
            request_id=request.request_id,
            policy_version=policy_version,
            request_hash=request_hash,
        )

