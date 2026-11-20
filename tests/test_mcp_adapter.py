from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters
from agentgate.mcp_server import LocalMCPGatewayAdapter, create_mcp_server
from agentgate.models import Decision, Role


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_mcp_adapter_routes_an_allowed_file_read_through_gateway(app):
    adapter = LocalMCPGatewayAdapter(app, subject_id="codex-test", role=Role.OPERATOR)

    result = adapter.read_project_file("public/welcome.txt")

    assert result["decision"] == Decision.ALLOW.value
    assert result["execution"]["status"] == "SUCCEEDED"
    assert app.registry.execution_counts["file.read"] == 1


def test_mcp_adapter_blocks_private_file_before_execution(app):
    adapter = LocalMCPGatewayAdapter(app, subject_id="codex-test", role=Role.OPERATOR)

    result = adapter.read_project_file("private/secret.txt")

    assert result["decision"] == Decision.DENY.value
    assert result["reason_code"] == "RESOURCE_OUT_OF_SCOPE"
    assert app.registry.execution_counts["file.read"] == 0


def test_mcp_adapter_creates_an_approval_and_exposes_its_status(app):
    adapter = LocalMCPGatewayAdapter(app, subject_id="codex-test", role=Role.OPERATOR)

    pending = adapter.send_review_notice(
        ["reviewer@example.test"], "Demo review", "Please review this simulated notice."
    )
    status = adapter.get_approval_status(pending["approval_id"])

    assert pending["decision"] == Decision.REQUIRE_APPROVAL.value
    assert status["status"] == "PENDING"
    assert app.registry.execution_counts["mail.send"] == 0


def test_mcp_server_advertises_the_five_agentgate_tools(app):
    adapter = LocalMCPGatewayAdapter(app, subject_id="codex-test", role=Role.OPERATOR)
    server = create_mcp_server(adapter)

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "read_project_file",
        "query_project_data",
        "send_review_notice",
        "get_approval_status",
        "get_audit_trace",
    }


def test_mcp_stdio_server_handles_a_real_tool_call(tmp_path):
    async def call_server():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agentgate.mcp_server"],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "AGENTGATE_PROJECT_ROOT": str(PROJECT_ROOT),
                "AGENTGATE_RUNTIME_ROOT": str(tmp_path / "runtime"),
            },
        )
        async with Client(parameters) as client:
            tools = await client.list_tools()
            result = await client.call_tool(
                "read_project_file", {"path": "public/welcome.txt"}
            )
            return tools, result

    tools, result = asyncio.run(call_server())

    assert "read_project_file" in {tool.name for tool in tools.tools}
    assert result.structured_content["decision"] == Decision.ALLOW.value
