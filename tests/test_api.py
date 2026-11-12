from __future__ import annotations

import asyncio
from pathlib import Path

from agentgate.api import ApprovalDecisionInput, ApprovedExecutionInput, create_api
from agentgate.models import ApprovalStatus, Decision, Role, ToolCallRequest


def endpoint(api, path: str, method: str):
    for route in api.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route: {method} {path}")


def test_openapi_declares_core_routes_and_strict_request_schema(app):
    api = create_api(app)

    schema = api.openapi()

    assert schema["info"]["title"] == "AgentGate API"
    assert "/health" in schema["paths"]
    assert "/v1/requests" in schema["paths"]
    assert "/v1/approvals/{approval_id}/grant" in schema["paths"]
    assert "/v1/approvals/{approval_id}/deny" in schema["paths"]
    assert "/v1/approvals/{approval_id}/execute" in schema["paths"]
    assert "/v1/approvals" in schema["paths"]
    assert "/v1/approvals/{approval_id}" in schema["paths"]
    assert "/v1/audit/recent" in schema["paths"]
    assert "/v1/traces/{trace_id}" in schema["paths"]
    assert schema["components"]["schemas"]["ToolCallRequest"]["additionalProperties"] is False


def test_dashboard_is_packaged_and_root_route_returns_it(app):
    api = create_api(app)

    response = asyncio.run(endpoint(api, "/", "GET")())

    dashboard_path = Path(response.path)
    assert dashboard_path.is_file()
    assert "AgentGate · 安全控制台" in dashboard_path.read_text(encoding="utf-8")
    assert (dashboard_path.parent / "styles.css").is_file()
    assert (dashboard_path.parent / "app.js").is_file()


def test_api_endpoints_complete_request_approval_execution_and_audit_flow(app):
    api = create_api(app)
    request = ToolCallRequest(
        subject_id="operator-web",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "Web demo",
            "body": "Synthetic message.",
        },
    )

    pending = asyncio.run(endpoint(api, "/v1/requests", "POST")(request))
    records = asyncio.run(
        endpoint(api, "/v1/approvals", "GET")(status=ApprovalStatus.PENDING, limit=100)
    )
    grant = asyncio.run(
        endpoint(api, "/v1/approvals/{approval_id}/grant", "POST")(
            pending.approval_id,
            ApprovalDecisionInput(
                approver_id="approver-web",
                approver_role=Role.APPROVER,
                reason="integration test",
            ),
        )
    )
    executed = asyncio.run(
        endpoint(api, "/v1/approvals/{approval_id}/execute", "POST")(
            pending.approval_id,
            ApprovedExecutionInput(request=request, token=grant.token),
        )
    )
    trace = asyncio.run(endpoint(api, "/v1/traces/{trace_id}", "GET")(request.trace_id))
    recent = asyncio.run(endpoint(api, "/v1/audit/recent", "GET")(limit=100))

    assert pending.decision is Decision.REQUIRE_APPROVAL
    assert [record.approval_id for record in records] == [pending.approval_id]
    assert executed.decision is Decision.ALLOW
    assert executed.execution is not None
    assert len(trace) == 6
    assert {event.event_id for event in trace}.issubset({event.event_id for event in recent})

