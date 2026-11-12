from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    OPERATOR = "operator"
    APPROVER = "approver"
    AUDITOR = "auditor"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReasonCode(StrEnum):
    ALLOWED = "ALLOWED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    RESOURCE_OUT_OF_SCOPE = "RESOURCE_OUT_OF_SCOPE"
    PARAMETER_INVALID = "PARAMETER_INVALID"
    HARD_LIMIT_EXCEEDED = "HARD_LIMIT_EXCEEDED"
    SENSITIVE_DATA_DETECTED = "SENSITIVE_DATA_DETECTED"
    APPROVAL_NOT_FOUND = "APPROVAL_NOT_FOUND"
    APPROVAL_NOT_PENDING = "APPROVAL_NOT_PENDING"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_HASH_MISMATCH = "APPROVAL_HASH_MISMATCH"
    APPROVAL_TOKEN_INVALID = "APPROVAL_TOKEN_INVALID"
    APPROVAL_ALREADY_USED = "APPROVAL_ALREADY_USED"
    SELF_APPROVAL_FORBIDDEN = "SELF_APPROVAL_FORBIDDEN"
    AUDIT_FAILURE = "AUDIT_FAILURE"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ExecutionStatus(StrEnum):
    NOT_EXECUTED = "NOT_EXECUTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AuditEventType(StrEnum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    NORMALIZATION_REJECTED = "NORMALIZATION_REJECTED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    REQUEST_DENIED = "REQUEST_DENIED"
    APPROVAL_CREATED = "APPROVAL_CREATED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    APPROVAL_VALIDATION_FAILED = "APPROVAL_VALIDATION_FAILED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class ToolCallRequest(StrictModel):
    subject_id: str = Field(min_length=1, max_length=128)
    role: Role
    tool_name: str = Field(min_length=1, max_length=128)
    parameters: dict[str, Any]
    session_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)
    trace_id: str = Field(default_factory=new_id)
    request_id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)


class NormalizedToolCall(StrictModel):
    subject_id: str
    role: Role
    tool_name: str
    parameters: dict[str, Any]
    session_id: str | None
    idempotency_key: str | None
    trace_id: str
    request_id: str
    policy_version: str
    request_hash: str


class PolicyDecision(StrictModel):
    decision: Decision
    reason_code: ReasonCode
    reason: str
    risk_level: RiskLevel
    matched_rule: str
    policy_version: str


class ToolExecutionResult(StrictModel):
    status: ExecutionStatus
    output: dict[str, Any] | None = None
    summary: str


class GatewayResponse(StrictModel):
    trace_id: str
    request_id: str
    decision: Decision
    reason_code: ReasonCode
    reason: str
    risk_level: RiskLevel
    approval_id: str | None = None
    execution: ToolExecutionResult | None = None


class ApprovalGrant(StrictModel):
    approval_id: str
    token: str
    expires_at: datetime


class ApprovalRecord(StrictModel):
    approval_id: str
    trace_id: str
    request_id: str
    subject_id: str
    role: Role
    tool_name: str
    request_hash: str
    policy_version: str
    parameters: dict[str, Any]
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    approver_id: str | None = None
    decision_reason: str | None = None
    used_at: datetime | None = None


class AuditEvent(StrictModel):
    event_id: str = Field(default_factory=new_id)
    event_type: AuditEventType
    trace_id: str
    request_id: str
    occurred_at: datetime = Field(default_factory=utc_now)
    parent_event_id: str | None = None
    subject_id: str | None = None
    role: Role | None = None
    tool_name: str | None = None
    decision: Decision | None = None
    reason_code: ReasonCode | None = None
    risk_level: RiskLevel | None = None
    parameter_hash: str | None = None
    policy_version: str | None = None
    approval_id: str | None = None
    execution_status: ExecutionStatus | None = None
    details: dict[str, Any] = Field(default_factory=dict)

