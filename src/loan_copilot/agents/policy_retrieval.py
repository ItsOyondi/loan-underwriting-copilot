"""Retrieve policy clauses and similar cases for this industry and request."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.domain.retrieval import search_policy, search_precedents
from loan_copilot.llm import complete
from loan_copilot.schemas import PolicyContext
from loan_copilot.tools.local_tools import search_policy as policy_tool
from loan_copilot.tools.local_tools import search_precedents as precedent_tool


def policy_retrieval(state: dict) -> dict:
    if state.get("stop_reason") or not state.get("intake"):
        return {}
    intake = state["intake"]
    query = f"{intake['industry']} {intake['purpose']} DSCR Debt/EBITDA covenant ${intake['requested_amount']}"
    # The same functions are exposed as LangChain tools for function calling.
    policies = search_policy(query)
    precedents = search_precedents(query, industry=intake["industry"])
    tool_check = policy_tool.invoke({"query": intake["industry"]})
    precedent_tool.invoke({"query": intake["purpose"], "industry": intake["industry"]})
    narrative = f"Retrieved {len(policies)} policy passages and {len(precedents)} precedents. Tool call returned {len(tool_check)} characters."
    offline = PolicyContext(policies=policies, precedents=precedents, narrative=narrative)
    model = complete(
        "mini",
        PolicyContext,
        "Summarize which policy clauses and precedents apply. Do not drop citations.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline.model_copy(update={"narrative": model.narrative or offline.narrative})
    return {
        "policy": result.model_dump(),
        "audit_log": [audit(state["case_id"], "policy_retrieval", "complete", result.narrative[:240])],
    }
