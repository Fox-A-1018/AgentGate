from __future__ import annotations

import json
from pathlib import Path

from agentgate.application import build_application
from agentgate.models import Role, ToolCallRequest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def show(label: str, value) -> None:
    print(f"\n=== {label} ===")
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    app = build_application(PROJECT_ROOT)

    normal = ToolCallRequest(
        subject_id="demo-viewer",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "public/welcome.txt"},
    )
    show("正常文件读取", app.gateway.submit(normal))

    blocked = ToolCallRequest(
        subject_id="demo-viewer",
        role=Role.VIEWER,
        tool_name="file.read",
        parameters={"path": "private/secret.txt"},
    )
    show("越权文件读取", app.gateway.submit(blocked))

    mail = ToolCallRequest(
        subject_id="demo-operator",
        role=Role.OPERATOR,
        tool_name="mail.send",
        parameters={
            "recipients": ["reviewer@example.test"],
            "subject": "AgentGate demo",
            "body": "This is a simulated local-only message.",
        },
    )
    pending = app.gateway.submit(mail)
    show("需要审批的模拟消息", pending)
    grant = app.gateway.grant_approval(
        pending.approval_id or "",
        approver_id="demo-approver",
        approver_role=Role.APPROVER,
        reason="approved for the local demo",
    )
    show("审批凭证", grant)
    show("审批后执行", app.gateway.execute_approved(mail, grant.approval_id, grant.token))
    show(
        "调用链",
        [event.model_dump(mode="json") for event in app.gateway.trace(mail.trace_id)],
    )


if __name__ == "__main__":
    main()

