"""Interpret ratios that Financial Calcs computed from the uploaded statements."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.domain.ratios import calculate_ratios
from loan_copilot.llm import complete
from loan_copilot.schemas import FinancialAssessment


def financial_assessment(state: dict) -> dict:
    if state.get("stop_reason") or not state.get("intake"):
        return {}
    ratios = calculate_ratios(state["intake"]["years"])
    latest = ratios[-1]
    strengths = []
    weaknesses = []
    if (latest.get("dscr") or 0) >= 1.5:
        strengths.append(f"DSCR is {latest['dscr']}x, above the 1.25x policy floor.")
    elif (latest.get("dscr") or 0) >= 1.25:
        weaknesses.append(f"DSCR is {latest['dscr']}x, only slightly above 1.25x.")
    else:
        weaknesses.append(f"DSCR is {latest['dscr']}x, below the 1.25x policy floor.")
    if (latest.get("debt_to_ebitda") or 0) <= 3.0:
        strengths.append(f"Debt/EBITDA is {latest['debt_to_ebitda']}x.")
    else:
        weaknesses.append(f"Debt/EBITDA is {latest['debt_to_ebitda']}x.")
    if latest.get("revenue_growth"):
        strengths.append(f"Revenue growth versus the prior year is {latest['revenue_growth']}.")
    offline = FinancialAssessment(
        ratios=ratios,
        strengths=strengths,
        weaknesses=weaknesses,
        narrative="Figures are from calculate_ratios on the uploaded financial statements. " + " ".join(strengths + weaknesses),
    )
    model = complete(
        "full",
        FinancialAssessment,
        "Explain the ratios. Do not change any numeric ratio.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline.model_copy(update={"narrative": model.narrative or offline.narrative})
    return {
        "financials": result.model_dump(),
        "audit_log": [audit(state["case_id"], "financial_assessment", "complete", result.narrative[:240])],
    }
