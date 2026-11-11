"""Choose the approver from the authority matrix."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.domain.authority import lookup_authority
from loan_copilot.llm import complete
from loan_copilot.schemas import ApprovalRoute


def approval_routing(state: dict) -> dict:
    if state.get("stop_reason") or not state.get("risk"):
        return {}
    amount = state["intake"]["requested_amount"]
    grade = state["risk"]["risk_grade"]
    level = lookup_authority(amount, grade)
    conditions = []
    if state["risk"]["recommendation"] == "approve_with_conditions":
        conditions.append("Waiver of the pro-forma covenant breach, with a quarterly compliance certificate.")
    if state["risk"]["policy_exceptions"]:
        conditions.append("Name each covenant breach in the approval conditions.")
    offline = ApprovalRoute(
        approver_level=level,
        amount=amount,
        risk_grade=grade,
        conditions=conditions,
        justification=f"${amount:,.0f} at risk grade {grade} routes to {level}.",
    )
    model = complete(
        "mini",
        ApprovalRoute,
        "Keep the approver_level. You may clarify the justification.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline.model_copy(update={"justification": model.justification or offline.justification})
    return {
        "route": result.model_dump(),
        "status": "final_approval",
        "audit_log": [audit(state["case_id"], "approval_routing", "complete", result.justification)],
    }
