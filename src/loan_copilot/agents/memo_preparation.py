"""Draft the credit memo from the case state."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.llm import complete
from loan_copilot.schemas import CreditMemo


def _markdown(state: dict) -> str:
    intake = state["intake"]
    financials = state.get("financials") or {}
    covenants = state.get("covenants") or {}
    risk = state.get("risk") or {}
    policy = state.get("policy") or {}
    latest = (financials.get("ratios") or [{}])[-1]
    precedent_titles = ", ".join(item.get("title", "") for item in policy.get("precedents") or []) or "none"
    feedback = (state.get("feedback") or {}).get("memo_review", "")
    lines = [
        f"# Credit memo: {intake['legal_name']}",
        "",
        f"Request: ${intake['requested_amount']:,.0f} for {intake['tenor_years']} years. {intake['purpose']}.",
        f"Collateral: {intake['collateral']}.",
        f"Industry: {intake['industry']}. Bureau score: {intake['bureau_score']}.",
        "",
        "## Financial analysis",
        f"Latest DSCR {latest.get('dscr')}x. Debt/EBITDA {latest.get('debt_to_ebitda')}x. "
        f"Current ratio {latest.get('current_ratio')}x. Interest coverage {latest.get('interest_coverage')}x.",
        financials.get("narrative", ""),
        "",
        "## Covenants",
        covenants.get("narrative", ""),
        "",
        "## Risk",
        f"Grade {risk.get('risk_grade')}. Recommendation: {risk.get('recommendation')}.",
        risk.get("narrative", ""),
        "",
        "## Policy and precedents",
        policy.get("narrative", ""),
        f"Precedents consulted: {precedent_titles}.",
        "",
        f"## Recommendation",
        str(risk.get("recommendation", "")),
    ]
    if feedback:
        lines.extend(["", f"Reviewer note: {feedback}"])
    return "\n".join(lines)


def memo_preparation(state: dict) -> dict:
    if state.get("stop_reason") or not state.get("risk"):
        return {}
    markdown = _markdown(state)
    offline = CreditMemo(markdown=markdown, recommendation=state["risk"]["recommendation"])
    model = complete(
        "full",
        CreditMemo,
        "Improve the prose of the markdown memo. Keep every figure and the recommendation.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline
    if model is not None and model.markdown:
        result = offline.model_copy(update={"markdown": model.markdown})
    return {
        "memo": result.model_dump(),
        "status": "memo_review",
        "audit_log": [audit(state["case_id"], "memo_preparation", "complete", "Credit memo drafted")],
    }
