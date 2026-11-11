"""Grade the case from tool results. Grades follow the covenant outcome."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.llm import complete
from loan_copilot.schemas import RiskAssessment


def _grade(breaches: list[str]) -> tuple[int, str]:
    current = [name for name in breaches if not name.startswith("pro forma")]
    pro_forma = [name for name in breaches if name.startswith("pro forma")]
    if current:
        return 8, "decline"
    if pro_forma:
        return 6, "approve_with_conditions"
    return 3, "approve"


def risk_synthesis(state: dict) -> dict:
    if state.get("stop_reason") or not state.get("intake"):
        return {}
    intake = state["intake"]
    covenants = state.get("covenants") or {"breaches": [], "narrative": ""}
    breaches = covenants.get("breaches", [])
    grade, recommendation = _grade(breaches)
    facilities = intake.get("facilities") or []
    outstanding = sum(item.get("outstanding", 0) for item in facilities)
    risks = list(breaches)
    if not intake.get("name_matches_customer"):
        risks.append("Borrower name on the request does not match the customer record.")
    if not risks:
        risks.append("No policy breach on current or pro-forma tests.")
    mitigants = []
    if facilities:
        mitigants.append(f"Existing outstanding balance on book is ${outstanding:,.0f}.")
    if intake.get("related_parties"):
        mitigants.append("Related parties are disclosed on the customer record.")
    feedback = (state.get("feedback") or {}).get("risk_review", "")
    narrative = (
        f"Risk grade {grade}. Recommendation: {recommendation}. "
        f"Customer {intake['legal_name']} ({intake['industry']}). "
        + covenants.get("narrative", "")
    )
    if feedback:
        narrative += f" Reviewer feedback: {feedback}"
    offline = RiskAssessment(
        risk_grade=grade,
        recommendation=recommendation,
        key_risks=risks,
        mitigants=mitigants,
        policy_exceptions=breaches,
        narrative=narrative,
    )
    model = complete(
        "full",
        RiskAssessment,
        "Write the narrative only. Do not change risk_grade or recommendation.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline.model_copy(update={"narrative": model.narrative or offline.narrative})
    return {
        "risk": result.model_dump(),
        "status": "risk_review",
        "audit_log": [audit(state["case_id"], "risk_synthesis", "complete", result.narrative[:240])],
    }
