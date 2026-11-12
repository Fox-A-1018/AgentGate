from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentgate.approval import ApprovalService
from agentgate.audit import AuditRepository
from agentgate.executor import ToolRegistry
from agentgate.gateway import AgentGateGateway
from agentgate.normalizers import NormalizerRegistry
from agentgate.policy import PolicyEngine
from agentgate.policy.config import PolicyConfig
from agentgate.tools import build_default_registry, initialize_business_database


@dataclass(slots=True)
class AgentGateApplication:
    gateway: AgentGateGateway
    registry: ToolRegistry
    audit: AuditRepository
    approvals: ApprovalService


def build_application(
    project_root: str | Path,
    runtime_root: str | Path | None = None,
    policy_path: str | Path | None = None,
) -> AgentGateApplication:
    project_root = Path(project_root)
    runtime_root = Path(runtime_root) if runtime_root else project_root / "data" / "runtime"
    policy_path = Path(policy_path) if policy_path else project_root / "policies" / "default.json"
    runtime_root.mkdir(parents=True, exist_ok=True)

    state_database = runtime_root / "agentgate.sqlite3"
    business_database = initialize_business_database(runtime_root / "business.sqlite3")
    sandbox_root = project_root / "data" / "fixtures" / "sandbox"
    outbox_path = runtime_root / "outbox.jsonl"

    audit = AuditRepository(state_database)
    approvals = ApprovalService(state_database)
    registry = build_default_registry(sandbox_root, business_database, outbox_path)
    policy = PolicyEngine(PolicyConfig.from_json(policy_path))
    gateway = AgentGateGateway(
        normalizers=NormalizerRegistry(),
        policy=policy,
        registry=registry,
        audit=audit,
        approvals=approvals,
    )
    return AgentGateApplication(
        gateway=gateway,
        registry=registry,
        audit=audit,
        approvals=approvals,
    )

