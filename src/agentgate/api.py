from __future__ import annotations

from pydantic import Field

from agentgate.application import AgentGateApplication
from agentgate.errors import ApprovalError
from agentgate.models import (
    ApprovalGrant,
    AuditEvent,
    GatewayResponse,
    Role,
    StrictModel,
    ToolCallRequest,
)


class ApprovalDecisionInput(StrictModel):
    approver_id: str = Field(min_length=1, max_length=128)
    approver_role: Role
    reason: str | None = Field(default=None, max_length=1000)


class ApprovedExecutionInput(StrictModel):
    request: ToolCallRequest
    token: str = Field(min_length=1, max_length=512)


def create_api(application: AgentGateApplication):
    from fastapi import FastAPI, HTTPException

    api = FastAPI(
        title="AgentGate API",
        version="0.1.0",
        description="Local-only API for deterministic agent tool-call authorization and audit.",
    )

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "policy_version": application.gateway.policy.version}

    @api.post("/v1/requests", response_model=GatewayResponse)
    async def submit(request: ToolCallRequest) -> GatewayResponse:
        return application.gateway.submit(request)

    @api.post("/v1/approvals/{approval_id}/grant", response_model=ApprovalGrant)
    async def grant(approval_id: str, body: ApprovalDecisionInput) -> ApprovalGrant:
        try:
            return application.gateway.grant_approval(
                approval_id,
                approver_id=body.approver_id,
                approver_role=body.approver_role,
                reason=body.reason,
            )
        except ApprovalError as exc:
            raise HTTPException(
                status_code=409,
                detail={"reason_code": exc.reason_code.value, "message": exc.message},
            ) from exc

    @api.post("/v1/approvals/{approval_id}/deny")
    async def deny(approval_id: str, body: ApprovalDecisionInput):
        try:
            return application.gateway.deny_approval(
                approval_id,
                approver_id=body.approver_id,
                approver_role=body.approver_role,
                reason=body.reason,
            )
        except ApprovalError as exc:
            raise HTTPException(
                status_code=409,
                detail={"reason_code": exc.reason_code.value, "message": exc.message},
            ) from exc

    @api.post("/v1/approvals/{approval_id}/execute", response_model=GatewayResponse)
    async def execute(approval_id: str, body: ApprovedExecutionInput) -> GatewayResponse:
        return application.gateway.execute_approved(body.request, approval_id, body.token)

    @api.get("/v1/traces/{trace_id}", response_model=list[AuditEvent])
    async def trace(trace_id: str) -> list[AuditEvent]:
        return application.gateway.trace(trace_id)

    return api

