from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentgate.models import Decision, ReasonCode, Role, ToolCallRequest


CASES_PATH = Path(__file__).parent / "security_cases" / "cases.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_structured_security_case(app, case):
    request = ToolCallRequest(
        subject_id=f"case-{case['id'].lower()}",
        role=Role(case["role"]),
        tool_name=case["tool_name"],
        parameters=case["parameters"],
    )

    response = app.gateway.submit(request)

    assert response.decision is Decision(case["expected_decision"])
    assert response.reason_code is ReasonCode(case["expected_reason_code"])
    if response.decision is not Decision.ALLOW:
        assert app.registry.execution_counts[case["tool_name"]] == 0
