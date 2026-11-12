from __future__ import annotations

from agentgate.approval import ApprovalService
from agentgate.gateway import AgentGateGateway
from agentgate.models import Decision, ReasonCode, Role, ToolCallRequest
from agentgate.normalizers import NormalizerRegistry
from agentgate.policy import PolicyEngine
from agentgate.policy.config import PolicyConfig
from agentgate.tools import build_default_registry, initialize_business_database


class FailingAuditRepository:
    def record(self, event):
        raise OSError("simulated audit failure")

    def list_trace(self, trace_id):
        return []


def test_audit_failure_blocks_tool_execution(tmp_path):
    project_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    business_db = initialize_business_database(tmp_path / "business.sqlite3")
    registry = build_default_registry(
        project_root / "data" / "fixtures" / "sandbox",
        business_db,
        tmp_path / "outbox.jsonl",
    )
    gateway = AgentGateGateway(
        normalizers=NormalizerRegistry(),
        policy=PolicyEngine(PolicyConfig.from_json(project_root / "policies" / "default.json")),
        registry=registry,
        audit=FailingAuditRepository(),
        approvals=ApprovalService(tmp_path / "state.sqlite3"),
    )
    request = ToolCallRequest(
        subject_id="viewer-1",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "public/welcome.txt"},
    )

    response = gateway.submit(request)

    assert response.decision is Decision.DENY
    assert response.reason_code is ReasonCode.AUDIT_FAILURE
    assert registry.execution_counts["file.read"] == 0

