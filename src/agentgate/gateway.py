from __future__ import annotations

from typing import Any

from agentgate.approval import ApprovalService
from agentgate.audit import AuditRepository
from agentgate.errors import ApprovalError, IdempotencyError, NormalizationError, ToolExecutionError
from agentgate.executor import ToolRegistry
from agentgate.idempotency import IdempotencyService
from agentgate.models import (
    ApprovalGrant,
    ApprovalRecord,
    AuditEvent,
    AuditEventType,
    Decision,
    ExecutionStatus,
    GatewayResponse,
    NormalizedToolCall,
    PolicyDecision,
    ReasonCode,
    RiskLevel,
    Role,
    ToolCallRequest,
    ToolExecutionResult,
)
from agentgate.normalizers import NormalizerRegistry
from agentgate.policy import PolicyEngine


class AgentGateGateway:
    def __init__(
        self,
        normalizers: NormalizerRegistry,
        policy: PolicyEngine,
        registry: ToolRegistry,
        audit: AuditRepository,
        approvals: ApprovalService,
        idempotency: IdempotencyService,
    ) -> None:
        self.normalizers = normalizers
        self.policy = policy
        self.registry = registry
        self.audit = audit
        self.approvals = approvals
        self.idempotency = idempotency

    def submit(self, request: ToolCallRequest) -> GatewayResponse:
        if not self._record(
            AuditEvent(
                event_type=AuditEventType.REQUEST_RECEIVED,
                trace_id=request.trace_id,
                request_id=request.request_id,
                subject_id=request.subject_id,
                role=request.role,
                tool_name=request.tool_name,
                details={"parameter_keys": sorted(request.parameters)},
            )
        ):
            return self._audit_failure(request)

        try:
            call = self.normalizers.normalize(request, self.policy.version)
        except NormalizationError as exc:
            self._record(
                AuditEvent(
                    event_type=AuditEventType.NORMALIZATION_REJECTED,
                    trace_id=request.trace_id,
                    request_id=request.request_id,
                    subject_id=request.subject_id,
                    role=request.role,
                    tool_name=request.tool_name,
                    decision=Decision.DENY,
                    reason_code=exc.reason_code,
                    risk_level=RiskLevel.HIGH,
                    policy_version=self.policy.version,
                    details={"message": exc.message},
                )
            )
            return GatewayResponse(
                trace_id=request.trace_id,
                request_id=request.request_id,
                decision=Decision.DENY,
                reason_code=exc.reason_code,
                reason=exc.message,
                risk_level=RiskLevel.HIGH,
            )

        try:
            replay = self.idempotency.begin(call)
        except IdempotencyError as exc:
            response = GatewayResponse(
                trace_id=call.trace_id,
                request_id=call.request_id,
                decision=Decision.DENY,
                reason_code=exc.reason_code,
                reason=exc.message,
                risk_level=RiskLevel.HIGH,
            )
            self._record_idempotency_event(
                AuditEventType.IDEMPOTENCY_REJECTED,
                call,
                response,
            )
            return response
        except Exception:
            response = GatewayResponse(
                trace_id=call.trace_id,
                request_id=call.request_id,
                decision=Decision.DENY,
                reason_code=ReasonCode.IDEMPOTENCY_UNAVAILABLE,
                reason="request was blocked because the idempotency store is unavailable",
                risk_level=RiskLevel.CRITICAL,
            )
            self._record_idempotency_event(
                AuditEventType.IDEMPOTENCY_REJECTED,
                call,
                response,
            )
            return response
        if replay is not None:
            self._record_idempotency_event(
                AuditEventType.IDEMPOTENCY_REPLAYED,
                call,
                replay,
            )
            return replay

        decision = self.policy.evaluate(call)
        if not self._record_policy(call, decision):
            return self._remember(call, self._audit_failure(request))

        if decision.decision is Decision.DENY:
            self._record_denial(call, decision)
            return self._remember(call, self._response(call, decision))

        if decision.decision is Decision.REQUIRE_APPROVAL:
            approval = self.approvals.create(call)
            if not self._record(
                self._event(
                    AuditEventType.APPROVAL_CREATED,
                    call,
                    decision=decision,
                    approval_id=approval.approval_id,
                    details={"expires_at": approval.expires_at.isoformat()},
                )
            ):
                return self._remember(call, self._audit_failure(request))
            return self._remember(
                call,
                self._response(call, decision, approval_id=approval.approval_id),
            )

        return self._remember(call, self._execute(call, decision))

    def grant_approval(
        self,
        approval_id: str,
        approver_id: str,
        approver_role: Role,
        reason: str | None = None,
    ) -> ApprovalGrant:
        grant = self.approvals.approve(approval_id, approver_id, approver_role, reason)
        record = self.approvals.get(approval_id)
        if not self._record(
            AuditEvent(
                event_type=AuditEventType.APPROVAL_GRANTED,
                trace_id=record.trace_id,
                request_id=record.request_id,
                subject_id=record.subject_id,
                role=record.role,
                tool_name=record.tool_name,
                decision=Decision.REQUIRE_APPROVAL,
                reason_code=ReasonCode.APPROVAL_REQUIRED,
                risk_level=RiskLevel.HIGH,
                parameter_hash=record.request_hash,
                policy_version=record.policy_version,
                approval_id=record.approval_id,
                details={"approver_id": approver_id, "expires_at": grant.expires_at.isoformat()},
            )
        ):
            raise ApprovalError(ReasonCode.AUDIT_FAILURE, "approval audit event could not be written")
        return grant

    def deny_approval(
        self,
        approval_id: str,
        approver_id: str,
        approver_role: Role,
        reason: str | None = None,
    ) -> ApprovalRecord:
        record = self.approvals.deny(approval_id, approver_id, approver_role, reason)
        if not self._record(
            AuditEvent(
                event_type=AuditEventType.APPROVAL_DENIED,
                trace_id=record.trace_id,
                request_id=record.request_id,
                subject_id=record.subject_id,
                role=record.role,
                tool_name=record.tool_name,
                decision=Decision.DENY,
                reason_code=ReasonCode.APPROVAL_NOT_PENDING,
                risk_level=RiskLevel.HIGH,
                parameter_hash=record.request_hash,
                policy_version=record.policy_version,
                approval_id=record.approval_id,
                details={"approver_id": approver_id, "reason": reason},
            )
        ):
            raise ApprovalError(ReasonCode.AUDIT_FAILURE, "approval audit event could not be written")
        return record

    def execute_approved(
        self,
        request: ToolCallRequest,
        approval_id: str,
        token: str,
    ) -> GatewayResponse:
        try:
            call = self.normalizers.normalize(request, self.policy.version)
        except NormalizationError as exc:
            return GatewayResponse(
                trace_id=request.trace_id,
                request_id=request.request_id,
                decision=Decision.DENY,
                reason_code=exc.reason_code,
                reason=exc.message,
                risk_level=RiskLevel.HIGH,
                approval_id=approval_id,
            )

        current_decision = self.policy.evaluate(call)
        if current_decision.decision is Decision.DENY:
            self._record_denial(call, current_decision, approval_id=approval_id)
            return self._response(call, current_decision, approval_id=approval_id)

        try:
            self.approvals.consume(approval_id, token, call)
        except ApprovalError as exc:
            self._record(
                self._event(
                    AuditEventType.APPROVAL_VALIDATION_FAILED,
                    call,
                    decision=PolicyDecision(
                        decision=Decision.DENY,
                        reason_code=exc.reason_code,
                        reason=exc.message,
                        risk_level=RiskLevel.CRITICAL,
                        matched_rule="approval.validation",
                        policy_version=self.policy.version,
                    ),
                    approval_id=approval_id,
                )
            )
            return GatewayResponse(
                trace_id=call.trace_id,
                request_id=call.request_id,
                decision=Decision.DENY,
                reason_code=exc.reason_code,
                reason=exc.message,
                risk_level=RiskLevel.CRITICAL,
                approval_id=approval_id,
            )

        return self._execute(call, current_decision, approval_id=approval_id)

    def trace(self, trace_id: str) -> list[AuditEvent]:
        return self.audit.list_trace(trace_id)

    def _execute(
        self,
        call: NormalizedToolCall,
        decision: PolicyDecision,
        approval_id: str | None = None,
    ) -> GatewayResponse:
        if not self._record(
            self._event(
                AuditEventType.EXECUTION_STARTED,
                call,
                decision=decision,
                approval_id=approval_id,
                execution_status=ExecutionStatus.NOT_EXECUTED,
            )
        ):
            if approval_id:
                self.approvals.mark_complete(approval_id, succeeded=False)
            return GatewayResponse(
                trace_id=call.trace_id,
                request_id=call.request_id,
                decision=Decision.DENY,
                reason_code=ReasonCode.AUDIT_FAILURE,
                reason="execution was blocked because the pre-execution audit event failed",
                risk_level=RiskLevel.CRITICAL,
                approval_id=approval_id,
            )

        try:
            execution = self.registry.execute(call)
        except ToolExecutionError as exc:
            if approval_id:
                self.approvals.mark_complete(approval_id, succeeded=False)
            self._record(
                self._event(
                    AuditEventType.EXECUTION_FAILED,
                    call,
                    decision=decision,
                    approval_id=approval_id,
                    execution_status=ExecutionStatus.FAILED,
                    details={"reason_code": exc.reason_code.value, "message": exc.message},
                )
            )
            failed = ToolExecutionResult(
                status=ExecutionStatus.FAILED,
                output=None,
                summary=exc.message,
            )
            return GatewayResponse(
                trace_id=call.trace_id,
                request_id=call.request_id,
                decision=Decision.ALLOW,
                reason_code=ReasonCode.EXECUTION_FAILED,
                reason=exc.message,
                risk_level=decision.risk_level,
                approval_id=approval_id,
                execution=failed,
            )

        if approval_id:
            self.approvals.mark_complete(approval_id, succeeded=True)
        self._record(
            self._event(
                AuditEventType.EXECUTION_SUCCEEDED,
                call,
                decision=decision,
                approval_id=approval_id,
                execution_status=ExecutionStatus.SUCCEEDED,
                details={"summary": execution.summary},
            )
        )
        effective_decision = PolicyDecision(
            decision=Decision.ALLOW,
            reason_code=ReasonCode.ALLOWED,
            reason="approved request executed" if approval_id else decision.reason,
            risk_level=decision.risk_level,
            matched_rule=decision.matched_rule,
            policy_version=decision.policy_version,
        )
        return self._response(
            call,
            effective_decision,
            approval_id=approval_id,
            execution=execution,
        )

    def _record_policy(self, call: NormalizedToolCall, decision: PolicyDecision) -> bool:
        return self._record(
            self._event(AuditEventType.POLICY_EVALUATED, call, decision=decision)
        )

    def _record_denial(
        self,
        call: NormalizedToolCall,
        decision: PolicyDecision,
        approval_id: str | None = None,
    ) -> None:
        self._record(
            self._event(
                AuditEventType.REQUEST_DENIED,
                call,
                decision=decision,
                approval_id=approval_id,
            )
        )

    def _record(self, event: AuditEvent) -> bool:
        try:
            self.audit.record(event)
        except Exception:
            return False
        return True

    def _remember(self, call: NormalizedToolCall, response: GatewayResponse) -> GatewayResponse:
        try:
            self.idempotency.complete(call, response)
        except Exception:
            self._record_idempotency_event(
                AuditEventType.IDEMPOTENCY_REJECTED,
                call,
                GatewayResponse(
                    trace_id=call.trace_id,
                    request_id=call.request_id,
                    decision=Decision.DENY,
                    reason_code=ReasonCode.IDEMPOTENCY_UNAVAILABLE,
                    reason="idempotency result could not be persisted",
                    risk_level=RiskLevel.CRITICAL,
                ),
            )
        return response

    def _record_idempotency_event(
        self,
        event_type: AuditEventType,
        call: NormalizedToolCall,
        response: GatewayResponse,
    ) -> None:
        self._record(
            AuditEvent(
                event_type=event_type,
                trace_id=call.trace_id,
                request_id=call.request_id,
                subject_id=call.subject_id,
                role=call.role,
                tool_name=call.tool_name,
                decision=response.decision,
                reason_code=response.reason_code,
                risk_level=response.risk_level,
                parameter_hash=call.request_hash,
                policy_version=call.policy_version,
                details={
                    "idempotency_key_hash": self.idempotency.key_digest(call),
                    "original_trace_id": response.trace_id,
                },
            )
        )

    @staticmethod
    def _event(
        event_type: AuditEventType,
        call: NormalizedToolCall,
        decision: PolicyDecision | None = None,
        approval_id: str | None = None,
        execution_status: ExecutionStatus | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            event_type=event_type,
            trace_id=call.trace_id,
            request_id=call.request_id,
            subject_id=call.subject_id,
            role=call.role,
            tool_name=call.tool_name,
            decision=decision.decision if decision else None,
            reason_code=decision.reason_code if decision else None,
            risk_level=decision.risk_level if decision else None,
            parameter_hash=call.request_hash,
            policy_version=call.policy_version,
            approval_id=approval_id,
            execution_status=execution_status,
            details=details or {},
        )

    @staticmethod
    def _response(
        call: NormalizedToolCall,
        decision: PolicyDecision,
        approval_id: str | None = None,
        execution: ToolExecutionResult | None = None,
    ) -> GatewayResponse:
        return GatewayResponse(
            trace_id=call.trace_id,
            request_id=call.request_id,
            decision=decision.decision,
            reason_code=decision.reason_code,
            reason=decision.reason,
            risk_level=decision.risk_level,
            approval_id=approval_id,
            execution=execution,
        )

    @staticmethod
    def _audit_failure(request: ToolCallRequest) -> GatewayResponse:
        return GatewayResponse(
            trace_id=request.trace_id,
            request_id=request.request_id,
            decision=Decision.DENY,
            reason_code=ReasonCode.AUDIT_FAILURE,
            reason="request was blocked because the audit store is unavailable",
            risk_level=RiskLevel.CRITICAL,
        )

