"""Local stdio MCP server that exposes AgentGate-controlled demo tools.

The MCP host (for example Codex) can choose a tool, but it never calls the
simulated file, database, or message handler directly. Every call first enters
the existing AgentGate gateway and therefore receives the same policy,
approval, execution, and audit treatment as the web demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from agentgate.application import AgentGateApplication, build_application
from agentgate.errors import ApprovalError
from agentgate.models import ApprovalStatus, GatewayResponse, Role, ToolCallRequest


DEFAULT_SUBJECT_ID = "codex-local-user"
DEFAULT_ROLE = Role.OPERATOR


def _environment_role() -> Role:
    """Read a local demo role from configuration, never from an MCP tool argument."""
    value = os.environ.get("AGENTGATE_MCP_ROLE", DEFAULT_ROLE.value).strip().lower()
    try:
        return Role(value)
    except ValueError as exc:
        choices = ", ".join(role.value for role in Role)
        raise RuntimeError(f"AGENTGATE_MCP_ROLE must be one of: {choices}") from exc


def _environment_root() -> Path:
    return Path(os.environ.get("AGENTGATE_PROJECT_ROOT", Path.cwd())).resolve()


def _environment_runtime_root() -> Path | None:
    value = os.environ.get("AGENTGATE_RUNTIME_ROOT")
    return Path(value).resolve() if value else None


def _response_payload(response: GatewayResponse) -> dict[str, Any]:
    """Return a stable JSON-shaped result that an MCP host can reason about."""
    return response.model_dump(mode="json")


@dataclass(slots=True)
class LocalMCPGatewayAdapter:
    """Maps focused MCP tools to the internal AgentGate tool names."""

    application: AgentGateApplication
    subject_id: str = DEFAULT_SUBJECT_ID
    role: Role = DEFAULT_ROLE

    def read_project_file(self, path: str) -> dict[str, Any]:
        """Read one project file through the AgentGate file policy."""
        return self._submit("file.read", {"path": path})

    def query_project_data(
        self,
        table: str,
        fields: list[str],
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query a whitelisted demo table through field and row-limit policy."""
        return self._submit(
            "db.select",
            {
                "table": table,
                "fields": fields,
                "limit": limit,
                "filters": filters or {},
            },
        )

    def send_review_notice(self, recipients: list[str], subject: str, body: str) -> dict[str, Any]:
        """Request a simulated outbound notice; policy requires human approval."""
        return self._submit(
            "mail.send",
            {"recipients": recipients, "subject": subject, "body": body},
        )

    def get_approval_status(self, approval_id: str) -> dict[str, Any]:
        """Read the status of an approval that was created by a prior tool call."""
        try:
            record = self.application.approvals.get(approval_id)
        except ApprovalError as exc:
            return {
                "status": "NOT_FOUND",
                "approval_id": approval_id,
                "reason_code": exc.reason_code.value,
                "reason": exc.message,
            }
        return record.model_dump(mode="json")

    def get_audit_trace(self, trace_id: str) -> dict[str, Any]:
        """Return the auditable lifecycle of one AgentGate request trace."""
        events = self.application.gateway.trace(trace_id)
        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "events": [event.model_dump(mode="json") for event in events],
        }

    def _submit(self, tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        request = ToolCallRequest(
            subject_id=self.subject_id,
            role=self.role,
            tool_name=tool_name,
            parameters=parameters,
            session_id="codex-local-mcp",
        )
        return _response_payload(self.application.gateway.submit(request))


def build_local_adapter(
    project_root: str | Path | None = None,
    runtime_root: str | Path | None = None,
    subject_id: str | None = None,
    role: Role | None = None,
) -> LocalMCPGatewayAdapter:
    root = Path(project_root).resolve() if project_root else _environment_root()
    application = build_application(root, runtime_root=runtime_root or _environment_runtime_root())
    return LocalMCPGatewayAdapter(
        application=application,
        subject_id=subject_id or os.environ.get("AGENTGATE_MCP_SUBJECT", DEFAULT_SUBJECT_ID),
        role=role or _environment_role(),
    )


def create_mcp_server(adapter: LocalMCPGatewayAdapter | None = None) -> MCPServer:
    """Create a standard MCP server without starting it, making it easy to test."""
    adapter = adapter or build_local_adapter()
    server = MCPServer(
        "AgentGate Local",
        instructions=(
            "Use these tools for the local project-data demonstration. "
            "Every tool call is evaluated by AgentGate before any simulated action runs. "
            "If a response includes REQUIRE_APPROVAL, ask the user to approve it in the "
            "AgentGate dashboard, then use get_approval_status or get_audit_trace."
        ),
    )

    @server.tool()
    def read_project_file(path: str) -> dict[str, Any]:
        """Read one allowed project file, such as public/welcome.txt, through AgentGate."""
        return adapter.read_project_file(path)

    @server.tool()
    def query_project_data(
        table: str,
        fields: list[str],
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query whitelisted project data. Large queries may require dashboard approval."""
        return adapter.query_project_data(table, fields, limit, filters)

    @server.tool()
    def send_review_notice(recipients: list[str], subject: str, body: str) -> dict[str, Any]:
        """Request a simulated review notice. It never sends real email and requires approval."""
        return adapter.send_review_notice(recipients, subject, body)

    @server.tool()
    def get_approval_status(approval_id: str) -> dict[str, Any]:
        """Check whether a previously requested high-risk action is pending, approved, or completed."""
        return adapter.get_approval_status(approval_id)

    @server.tool()
    def get_audit_trace(trace_id: str) -> dict[str, Any]:
        """Inspect AgentGate audit events for a trace returned by an earlier tool call."""
        return adapter.get_audit_trace(trace_id)

    return server


def main() -> None:
    """Run as a stdio child process of an MCP host; do not print to stdout here."""
    create_mcp_server().run()


if __name__ == "__main__":
    main()
