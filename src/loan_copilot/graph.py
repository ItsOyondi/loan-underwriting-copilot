"""LangGraph: intake, three parallel analyses, then risk, memo, and approval."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from loan_copilot.agents.approval_routing import approval_routing
from loan_copilot.agents.common import audit
from loan_copilot.agents.covenant_testing import covenant_testing
from loan_copilot.agents.document_intake import document_intake
from loan_copilot.agents.financial_assessment import financial_assessment
from loan_copilot.agents.memo_preparation import memo_preparation
from loan_copilot.agents.policy_retrieval import policy_retrieval
from loan_copilot.agents.risk_synthesis import risk_synthesis
from loan_copilot.config import settings
from loan_copilot.memory import redis_store
from loan_copilot.state import LoanCaseState


def _pause(state: dict, checkpoint: str, options: list[str]) -> dict:
    decision = interrupt(
        {
            "checkpoint": checkpoint,
            "case_id": state["case_id"],
            "options": options,
            "risk": state.get("risk"),
            "route": state.get("route"),
            "memo_preview": ((state.get("memo") or {}).get("markdown") or "")[:800],
        }
    )
    if not isinstance(decision, dict):
        decision = {"action": str(decision), "comments": ""}
    action = decision.get("action") or "approve"
    comments = decision.get("comments") or ""
    redis_store.record_hitl_decision(state["case_id"], checkpoint, action, comments)
    counts = dict(state.get("revision_counts") or {})
    if action in {"revise", "send_back"}:
        counts[checkpoint] = counts.get(checkpoint, 0) + 1
    feedback = dict(state.get("feedback") or {})
    feedback[checkpoint] = comments
    return {
        "hitl_decisions": [{"checkpoint": checkpoint, "action": action, "comments": comments}],
        "revision_counts": counts,
        "feedback": feedback,
        "audit_log": [audit(state["case_id"], checkpoint, action, comments or action)],
    }


def hitl_risk_review(state: dict) -> dict:
    return _pause(state, "risk_review", ["approve", "revise", "reject"])


def hitl_memo_review(state: dict) -> dict:
    return _pause(state, "memo_review", ["approve", "revise"])


def hitl_final_approval(state: dict) -> dict:
    return _pause(state, "final_approval", ["approve", "approve_with_conditions", "decline", "send_back"])


def join_analysis(state: dict) -> dict:
    if state.get("stop_reason"):
        return {}
    return {"status": "analysis"}


def case_closed(state: dict) -> dict:
    return {
        "status": "rejected",
        "audit_log": [audit(state["case_id"], "case_closed", "rejected", "Reviewer rejected the case")],
    }


def exception_handler(state: dict) -> dict:
    reason = state.get("stop_reason") or "revision cap reached"
    return {
        "status": "failed",
        "stop_reason": reason,
        "audit_log": [audit(state["case_id"], "exception_handler", "failed", reason)],
    }


def record_decision(state: dict) -> dict:
    last = state["hitl_decisions"][-1]
    action = last["action"]
    final_status = "declined" if action == "decline" else "approved"
    redis_store.record_final_decision(state["case_id"], action, last.get("comments") or "")
    return {
        "status": final_status,
        "audit_log": [audit(state["case_id"], "record_decision", final_status, action)],
    }


def _last_action(state: dict) -> str:
    return state["hitl_decisions"][-1]["action"]


def route_after_join(state: dict) -> str:
    if state.get("stop_reason"):
        return "exception_handler"
    return "risk_synthesis"


def route_after_risk(state: dict) -> str:
    action = _last_action(state)
    if action == "reject":
        return "case_closed"
    if action == "revise":
        if state["revision_counts"].get("risk_review", 0) > settings.max_revisions:
            return "exception_handler"
        return "risk_synthesis"
    return "memo_preparation"


def route_after_memo(state: dict) -> str:
    action = _last_action(state)
    if action == "revise":
        if state["revision_counts"].get("memo_review", 0) > settings.max_revisions:
            return "exception_handler"
        return "memo_preparation"
    return "approval_routing"


def route_after_final(state: dict) -> str:
    action = _last_action(state)
    if action == "send_back":
        if state["revision_counts"].get("final_approval", 0) > settings.max_revisions:
            return "exception_handler"
        return "memo_preparation"
    return "record_decision"


def build_graph(checkpointer=None):
    """Compile the case graph. Pass a checkpointer so a human pause can be resumed."""
    builder = StateGraph(LoanCaseState)
    builder.add_node("document_intake", document_intake)
    builder.add_node("financial_assessment", financial_assessment)
    builder.add_node("covenant_testing", covenant_testing)
    builder.add_node("policy_retrieval", policy_retrieval)
    builder.add_node("join_analysis", join_analysis)
    builder.add_node("risk_synthesis", risk_synthesis)
    builder.add_node("hitl_risk_review", hitl_risk_review)
    builder.add_node("memo_preparation", memo_preparation)
    builder.add_node("hitl_memo_review", hitl_memo_review)
    builder.add_node("approval_routing", approval_routing)
    builder.add_node("hitl_final_approval", hitl_final_approval)
    builder.add_node("record_decision", record_decision)
    builder.add_node("case_closed", case_closed)
    builder.add_node("exception_handler", exception_handler)

    builder.set_entry_point("document_intake")
    builder.add_edge("document_intake", "financial_assessment")
    builder.add_edge("document_intake", "covenant_testing")
    builder.add_edge("document_intake", "policy_retrieval")
    builder.add_edge("financial_assessment", "join_analysis")
    builder.add_edge("covenant_testing", "join_analysis")
    builder.add_edge("policy_retrieval", "join_analysis")
    builder.add_conditional_edges("join_analysis", route_after_join, ["risk_synthesis", "exception_handler"])
    builder.add_edge("risk_synthesis", "hitl_risk_review")
    builder.add_conditional_edges(
        "hitl_risk_review",
        route_after_risk,
        ["risk_synthesis", "memo_preparation", "case_closed", "exception_handler"],
    )
    builder.add_edge("memo_preparation", "hitl_memo_review")
    builder.add_conditional_edges(
        "hitl_memo_review",
        route_after_memo,
        ["memo_preparation", "approval_routing", "exception_handler"],
    )
    builder.add_edge("approval_routing", "hitl_final_approval")
    builder.add_conditional_edges(
        "hitl_final_approval",
        route_after_final,
        ["memo_preparation", "record_decision", "exception_handler"],
    )
    builder.add_edge("record_decision", END)
    builder.add_edge("case_closed", END)
    builder.add_edge("exception_handler", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())
