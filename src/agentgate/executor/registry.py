from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from agentgate.errors import ToolExecutionError
from agentgate.models import (
    ExecutionStatus,
    NormalizedToolCall,
    ReasonCode,
    ToolExecutionResult,
)


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    """The only component that owns executable tool handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self.execution_counts: Counter[str] = Counter()

    def register(self, name: str, handler: ToolHandler) -> None:
        if name in self._handlers:
            raise ValueError(f"tool already registered: {name}")
        self._handlers[name] = handler

    def execute(self, call: NormalizedToolCall) -> ToolExecutionResult:
        handler = self._handlers.get(call.tool_name)
        if handler is None:
            raise ToolExecutionError(ReasonCode.UNKNOWN_TOOL, f"tool is not registered: {call.tool_name}")
        self.execution_counts[call.tool_name] += 1
        try:
            output = handler(call.parameters)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(ReasonCode.EXECUTION_FAILED, str(exc)) from exc
        return ToolExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            output=output,
            summary=f"{call.tool_name} completed",
        )

