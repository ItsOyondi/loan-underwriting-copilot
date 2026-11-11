"""Run one sample case in the terminal.

Examples, from the finUseCase folder:

    python scripts/run_case.py --case case_001_strong --auto-approve
    python scripts/run_case.py --case case_003_breach
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loan_copilot.config import settings
from loan_copilot.service import resume_case, start_case


def _ask(pending: dict) -> tuple[str, str]:
    options = ", ".join(pending.get("options") or [])
    print(f"\nCheckpoint: {pending.get('checkpoint')}")
    print(f"Options: {options}")
    if pending.get("risk"):
        risk = pending["risk"]
        print(f"Risk grade {risk.get('risk_grade')}: {risk.get('recommendation')}")
        print(risk.get("narrative", "")[:500])
    if pending.get("route"):
        print(f"Route: {pending['route'].get('approver_level')}")
    if pending.get("memo_preview"):
        print(pending["memo_preview"][:700])
    action = input("Decision: ").strip() or "approve"
    comments = input("Comments: ").strip()
    return action, comments


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a loan case through the copilot")
    parser.add_argument("--case", default="case_001_strong")
    parser.add_argument("--case-id", default="")
    parser.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args()
    case_id = args.case_id or f"{args.case}-{uuid.uuid4().hex[:8]}"
    mode = "Azure OpenAI" if settings.azure_ready else "offline tool results"
    print(f"Case {case_id} using {args.case} ({mode})")
    view = start_case(case_id, args.case)
    while view.get("pending"):
        pending = view["pending"]
        if args.auto_approve:
            action, comments = "approve", "auto"
            print(f"Auto-approved {pending.get('checkpoint')}")
        else:
            action, comments = _ask(pending)
        view = resume_case(case_id, action, comments)
    print(f"\nStatus: {view.get('status')}")
    if view.get("stop_reason"):
        print(f"Stop reason: {view['stop_reason']}")
    risk = view.get("risk") or {}
    if risk:
        print(f"Recommendation: {risk.get('recommendation')} (grade {risk.get('risk_grade')})")
    route = view.get("route") or {}
    if route:
        print(f"Approver: {route.get('approver_level')}")
    memo = (view.get("memo") or {}).get("markdown")
    if memo:
        print("\n" + memo)


if __name__ == "__main__":
    main()
