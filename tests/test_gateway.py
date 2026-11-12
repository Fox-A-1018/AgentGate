from __future__ import annotations

import json

import pytest

from agentgate.errors import ApprovalError
from agentgate.models import (
    AuditEventType,
    Decision,
    ExecutionStatus,
    ReasonCode,
    Role,
    ToolCallRequest,
)


def test_viewer_can_read_public_file(app):
    request = ToolCallRequest(
        subject_id="viewer-1",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "public/welcome.txt"},
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.ALLOW
    assert response.reason_code is ReasonCode.ALLOWED
    assert response.execution is not None
    assert response.execution.status is ExecutionStatus.SUCCEEDED
    assert "AgentGate public fixture" in response.execution.output["content"]
    assert app.registry.execution_counts["file.read"] == 1


def test_viewer_cannot_read_private_file_and_tool_is_not_called(app):
    request = ToolCallRequest(
        subject_id="viewer-1",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "private/secret.txt"},
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.RESOURCE_OUT_OF_SCOPE
    assert app.registry.execution_counts["file.read"] == 0


def test_parent_path_traversal_is_rejected_before_policy(app):
    request = ToolCallRequest(
        subject_id="viewer-1",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "public/../private/secret.txt"},
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.RESOURCE_OUT_OF_SCOPE
    assert app.registry.execution_counts["file.read"] == 0


def test_structured_database_query_is_allowed(app):
    request = ToolCallRequest(
        subject_id="analyst-1",
        role=Role.ANALYST,
        tool_name="db.select",
        parameters={
            "table": "inventory",
            "fields": ["sku", "stock"],
            "filters": {},
            "limit": 20,
        },
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.ALLOW
    assert response.execution.output["row_count"] == 3
    assert set(response.execution.output["rows"][0]) == {"sku", "stock"}


def test_raw_sql_is_rejected(app):
    request = ToolCallRequest(
        subject_id="analyst-1",
        role=Role.ANALYST,
        tool_name="db.select",
        parameters={"sql": "SELECT * FROM inventory"},
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.PARAMETER_INVALID
    assert app.registry.execution_counts["db.select"] == 0


def test_database_soft_limit_requires_approval(app):
    request = ToolCallRequest(
        subject_id="analyst-1",
        role=Role.ANALYST,
        tool_name="db.select",
        parameters={
            "table": "inventory",
            "fields": ["sku"],
            "filters": {},
            "limit": 101,
        },
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.REQUIRE_APPROVAL
    assert response.approval_id
    assert app.registry.execution_counts["db.select"] == 0


def test_database_hard_limit_is_denied(app):
    request = ToolCallRequest(
        subject_id="analyst-1",
        role=Role.ANALYST,
        tool_name="db.select",
        parameters={
            "table": "inventory",
            "fields": ["sku"],
            "filters": {},
            "limit": 501,
        },
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.HARD_LIMIT_EXCEEDED
    assert app.registry.execution_counts["db.select"] == 0


def test_operator_mail_requires_approval_and_executes_once(app, tmp_path):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Demo",
            "body": "Synthetic content only.",
        },
    )
    pending = app.gateway.submit(request)
    assert pending.decision is Decision.REQUIRE_APPROVAL
    assert app.registry.execution_counts["mail.send"] == 0

    grant = app.gateway.grant_approval(
        pending.approval_id,
        approver_id="approver-1",
        approver_role=Role.APPROVER,
        reason="local demo approved",
    )
    executed = app.gateway.execute_approved(request, grant.approval_id, grant.token)

    assert executed.decision is Decision.ALLOW
    assert executed.execution.status is ExecutionStatus.SUCCEEDED
    assert app.registry.execution_counts["mail.send"] == 1
    outbox = tmp_path / "runtime" / "outbox.jsonl"
    records = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert "body" not in records[0]
    assert records[0]["body_length"] == len("Synthetic content only.")

    replay = app.gateway.execute_approved(request, grant.approval_id, grant.token)
    assert replay.decision is Decision.DENY
    assert replay.reason_code is ReasonCode.APPROVAL_ALREADY_USED
    assert app.registry.execution_counts["mail.send"] == 1
    assert len(outbox.read_text(encoding="utf-8").splitlines()) == 1


def test_approved_request_cannot_be_tampered(app):
    original = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Demo",
            "body": "Original content.",
        },
    )
    pending = app.gateway.submit(original)
    grant = app.gateway.grant_approval(
        pending.approval_id,
        approver_id="approver-1",
        approver_role=Role.APPROVER,
    )
    tampered = original.model_copy(
        update={
            "parameters": {
                "recipients": ["other@example.test"],
                "subject": "Demo",
                "body": "Original content.",
            }
        }
    )

    response = app.gateway.execute_approved(tampered, grant.approval_id, grant.token)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.APPROVAL_HASH_MISMATCH
    assert app.registry.execution_counts["mail.send"] == 0


def test_self_approval_is_forbidden(app):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Demo",
            "body": "Synthetic content only.",
        },
    )
    pending = app.gateway.submit(request)

    with pytest.raises(ApprovalError) as exc_info:
        app.gateway.grant_approval(
            pending.approval_id,
            approver_id="operator-1",
            approver_role=Role.APPROVER,
        )

    assert exc_info.value.reason_code is ReasonCode.SELF_APPROVAL_FORBIDDEN


def test_sensitive_mail_content_is_denied(app):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Credential",
            "body": "api_key=not-a-real-key",
        },
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.SENSITIVE_DATA_DETECTED
    assert app.registry.execution_counts["mail.send"] == 0


def test_unapproved_recipient_domain_is_denied(app):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.com"],
            "subject": "Demo",
            "body": "Synthetic content only.",
        },
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.RESOURCE_OUT_OF_SCOPE
    assert app.registry.execution_counts["mail.send"] == 0


def test_wrong_approval_token_is_denied_without_execution(app):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Demo",
            "body": "Synthetic content only.",
        },
    )
    pending = app.gateway.submit(request)
    grant = app.gateway.grant_approval(
        pending.approval_id,
        approver_id="approver-1",
        approver_role=Role.APPROVER,
    )

    response = app.gateway.execute_approved(request, grant.approval_id, "wrong-token")

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.APPROVAL_TOKEN_INVALID
    assert app.registry.execution_counts["mail.send"] == 0


def test_denied_approval_cannot_be_executed(app):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Demo",
            "body": "Synthetic content only.",
        },
    )
    pending = app.gateway.submit(request)
    app.gateway.deny_approval(
        pending.approval_id,
        approver_id="approver-1",
        approver_role=Role.APPROVER,
        reason="not needed",
    )

    response = app.gateway.execute_approved(request, pending.approval_id, "unused-token")

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.APPROVAL_NOT_PENDING
    assert app.registry.execution_counts["mail.send"] == 0


def test_non_approver_role_cannot_approve(app):
    request = ToolCallRequest(
        subject_id="operator-1",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Demo",
            "body": "Synthetic content only.",
        },
    )
    pending = app.gateway.submit(request)

    with pytest.raises(ApprovalError) as exc_info:
        app.gateway.grant_approval(
            pending.approval_id,
            approver_id="analyst-1",
            approver_role=Role.ANALYST,
        )

    assert exc_info.value.reason_code is ReasonCode.TOOL_NOT_ALLOWED
    assert app.registry.execution_counts["mail.send"] == 0


def test_trace_contains_ordered_security_events(app):
    request = ToolCallRequest(
        subject_id="viewer-1",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "public/welcome.txt"},
    )
    app.gateway.submit(request)

    event_types = [event.event_type for event in app.gateway.trace(request.trace_id)]

    assert event_types == [
        AuditEventType.REQUEST_RECEIVED,
        AuditEventType.POLICY_EVALUATED,
        AuditEventType.EXECUTION_STARTED,
        AuditEventType.EXECUTION_SUCCEEDED,
    ]

