from __future__ import annotations

from .models import ReasonCode


class AgentGateError(Exception):
    def __init__(self, reason_code: ReasonCode, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


class NormalizationError(AgentGateError):
    pass


class ApprovalError(AgentGateError):
    pass


class ToolExecutionError(AgentGateError):
    pass


class IdempotencyError(AgentGateError):
    pass

