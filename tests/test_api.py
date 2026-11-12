from __future__ import annotations

from agentgate.api import create_api


def test_openapi_declares_core_routes_and_strict_request_schema(app):
    api = create_api(app)

    schema = api.openapi()

    assert schema["info"]["title"] == "AgentGate API"
    assert "/health" in schema["paths"]
    assert "/v1/requests" in schema["paths"]
    assert "/v1/approvals/{approval_id}/grant" in schema["paths"]
    assert "/v1/approvals/{approval_id}/deny" in schema["paths"]
    assert "/v1/approvals/{approval_id}/execute" in schema["paths"]
    assert "/v1/traces/{trace_id}" in schema["paths"]
    assert schema["components"]["schemas"]["ToolCallRequest"]["additionalProperties"] is False

