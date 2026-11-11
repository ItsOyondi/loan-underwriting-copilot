"""Test current and pro-forma ratios against the covenant file."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.config import settings
from loan_copilot.domain.covenants import breach_names, evaluate_covenants
from loan_copilot.domain.ratios import calculate_ratios, pro_forma_debt_service
from loan_copilot.llm import complete
from loan_copilot.schemas import CovenantResult


def covenant_testing(state: dict) -> dict:
    if state.get("stop_reason") or not state.get("intake"):
        return {}
    intake = state["intake"]
    ratios = calculate_ratios(intake["years"])
    latest_year = max(intake["years"], key=lambda item: item["year"])
    pro_forma = pro_forma_debt_service(
        latest_year,
        intake["requested_amount"],
        intake["tenor_years"],
        settings.new_loan_rate,
    )
    current = evaluate_covenants(ratios[-1], label="current")
    pro_forma_results = evaluate_covenants(pro_forma, label="pro_forma")
    breaches = breach_names(current + pro_forma_results)
    narrative = "No covenant breaches." if not breaches else "Breaches: " + "; ".join(breaches) + "."
    offline = CovenantResult(current=current, pro_forma=pro_forma_results, breaches=breaches, narrative=narrative)
    model = complete(
        "mini",
        CovenantResult,
        "Describe the covenant tests. Do not change pass/fail results.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline.model_copy(update={"narrative": model.narrative or offline.narrative})
    return {
        "covenants": result.model_dump(),
        "audit_log": [audit(state["case_id"], "covenant_testing", "complete", result.narrative)],
    }
