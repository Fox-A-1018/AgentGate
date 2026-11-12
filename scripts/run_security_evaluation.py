from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agentgate.application import build_application
from agentgate.models import Decision, Role, ToolCallRequest


CASES_PATH = PROJECT_ROOT / "tests" / "security_cases" / "cases.json"


def percentile_95(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, int(0.95 * len(ordered) + 0.999999) - 1)
    return ordered[index]


def evaluate() -> dict:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = []
    runtime_root = PROJECT_ROOT / "data" / "runtime" / "evaluation"
    app = build_application(PROJECT_ROOT, runtime_root=runtime_root)
    for case in cases:
        request = ToolCallRequest(
            subject_id=f"evaluation-{case['id'].lower()}",
            role=Role(case["role"]),
            tool_name=case["tool_name"],
            parameters=case["parameters"],
        )
        started = perf_counter()
        response = app.gateway.submit(request)
        elapsed_ms = (perf_counter() - started) * 1000
        trace = app.gateway.trace(request.trace_id)
        correct = (
            response.decision.value == case["expected_decision"]
            and response.reason_code.value == case["expected_reason_code"]
        )
        audit_complete = bool(trace) and all(
            event.trace_id == request.trace_id
            and event.request_id == request.request_id
            and event.event_type
            and event.occurred_at
            for event in trace
        )
        results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_decision": case["expected_decision"],
                "actual_decision": response.decision.value,
                "expected_reason_code": case["expected_reason_code"],
                "actual_reason_code": response.reason_code.value,
                "correct": correct,
                "audit_complete": audit_complete,
                "latency_ms": round(elapsed_ms, 3),
            }
        )

    protected = [row for row in results if row["expected_decision"] != Decision.ALLOW.value]
    false_allows = [row for row in protected if row["actual_decision"] == Decision.ALLOW.value]
    latencies = [row["latency_ms"] for row in results]
    categories = Counter(row["category"] for row in results)
    return {
        "case_count": len(results),
        "category_counts": dict(sorted(categories.items())),
        "decision_and_reason_accuracy": sum(row["correct"] for row in results) / len(results),
        "protected_case_control_rate": 1 - len(false_allows) / len(protected),
        "false_allow_rate": len(false_allows) / len(protected),
        "audit_completeness_rate": sum(row["audit_complete"] for row in results) / len(results),
        "latency_ms": {
            "median": round(statistics.median(latencies), 3),
            "p95": round(percentile_95(latencies), 3),
            "maximum": round(max(latencies), 3),
        },
        "failures": [row for row in results if not row["correct"] or not row["audit_complete"]],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AgentGate against structured security cases.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
