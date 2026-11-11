"""Print the result of every sample case. Exit 1 when a case misses the catalog."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from loan_copilot.graph import build_graph
from loan_copilot.samples import load_catalog, outcome_errors, validate_catalog
from loan_copilot.service import execute


def main() -> int:
    problems = validate_catalog()
    if problems:
        print("Sample data does not match the catalog:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    graph = build_graph()
    failures = []
    print(f"{'case':<28} {'status':<12} {'grade':<6} {'recommendation':<24} approver")
    for case in load_catalog()["cases"]:
        view = execute(graph, f"report-{case['id']}", case["id"])
        risk = view.get("risk") or {}
        route = view.get("route") or {}
        grade = risk.get("risk_grade", "-")
        recommendation = risk.get("recommendation") or view.get("stop_reason") or "-"
        approver = route.get("approver_level", "-")
        print(f"{case['id']:<28} {view.get('status', '-'):<12} {str(grade):<6} {recommendation:<24} {approver}")
        failures.extend(outcome_errors(view, case))
    if failures:
        print()
        for failure in failures:
            print(failure)
        return 1
    print()
    print(f"{len(load_catalog()['cases'])} sample cases matched the catalog.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
