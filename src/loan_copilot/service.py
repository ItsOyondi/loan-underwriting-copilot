"""Start a sample case and resume it after each human checkpoint."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.types import Command

from loan_copilot.config import DATA, RUNTIME
from loan_copilot.graph import build_graph
from loan_copilot.observability import setup_observability
from loan_copilot.state import empty_state

_GRAPH = None


def case_directory(sample_case: str) -> Path:
    folder = DATA / "sample_cases" / sample_case
    if not folder.is_dir():
        raise FileNotFoundError(f"Sample case not found: {sample_case}")
    return folder


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        setup_observability()
        _GRAPH = build_graph(_checkpointer())
    return _GRAPH


def _checkpointer():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        connection = sqlite3.connect(str(RUNTIME / "checkpoints.sqlite"), check_same_thread=False)
        return SqliteSaver(connection)
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


def _config(case_id: str) -> dict:
    return {"configurable": {"thread_id": case_id}}


def pending_interrupt(case_id: str, graph=None):
    snapshot = (graph or get_graph()).get_state(_config(case_id))
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if interrupts:
        first = interrupts[0]
        return getattr(first, "value", first)
    for task in getattr(snapshot, "tasks", None) or ():
        found = getattr(task, "interrupts", None) or ()
        if found:
            return getattr(found[0], "value", found[0])
    return None


def _values(case_id: str, graph=None) -> dict:
    snapshot = (graph or get_graph()).get_state(_config(case_id))
    return dict(snapshot.values or {})


def execute(graph, case_id: str, sample_case: str, actions: list[str] | None = None) -> dict:
    """Run a case on a caller-supplied graph. Used by the CLI, the API, and tests."""
    graph.invoke(empty_state(case_id, str(case_directory(sample_case))), _config(case_id))
    view = _view(graph, case_id)
    queue = list(actions or [])
    while view.get("pending"):
        action = queue.pop(0) if queue else "approve"
        graph.invoke(Command(resume={"action": action, "comments": "mvp"}), _config(case_id))
        view = _view(graph, case_id)
    return view


def _view(graph, case_id: str) -> dict:
    values = _values(case_id, graph)
    return {
        "case_id": case_id,
        "status": values.get("status"),
        "stop_reason": values.get("stop_reason"),
        "pending": pending_interrupt(case_id, graph),
        "intake": values.get("intake"),
        "financials": values.get("financials"),
        "covenants": values.get("covenants"),
        "policy": values.get("policy"),
        "risk": values.get("risk"),
        "memo": values.get("memo"),
        "route": values.get("route"),
        "hitl_decisions": values.get("hitl_decisions", []),
        "audit_log": values.get("audit_log", []),
    }


def start_case(case_id: str, sample_case: str) -> dict:
    """Run until the first human checkpoint or the end of the graph."""
    get_graph().invoke(empty_state(case_id, str(case_directory(sample_case))), _config(case_id))
    return current_view(case_id)


def resume_case(case_id: str, action: str, comments: str = "") -> dict:
    """Continue a paused case with one reviewer decision."""
    get_graph().invoke(Command(resume={"action": action, "comments": comments}), _config(case_id))
    return current_view(case_id)


def run_to_end(case_id: str, sample_case: str, actions: list[str] | None = None) -> dict:
    """Finish a case. `actions` are used in order. Missing actions approve."""
    return execute(get_graph(), case_id, sample_case, actions)


def current_view(case_id: str) -> dict:
    return _view(get_graph(), case_id)
