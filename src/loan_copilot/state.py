"""Shared LangGraph state. List fields append. Other fields are replaced."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class LoanCaseState(TypedDict):
    case_id: str
    case_dir: str
    intake: dict | None
    financials: dict | None
    covenants: dict | None
    policy: dict | None
    risk: dict | None
    memo: dict | None
    route: dict | None
    hitl_decisions: Annotated[list[dict], operator.add]
    revision_counts: dict
    feedback: dict
    errors: Annotated[list[dict], operator.add]
    audit_log: Annotated[list[dict], operator.add]
    status: str
    stop_reason: str | None


def empty_state(case_id: str, case_dir: str) -> LoanCaseState:
    return {
        "case_id": case_id,
        "case_dir": case_dir,
        "intake": None,
        "financials": None,
        "covenants": None,
        "policy": None,
        "risk": None,
        "memo": None,
        "route": None,
        "hitl_decisions": [],
        "revision_counts": {},
        "feedback": {},
        "errors": [],
        "audit_log": [],
        "status": "intake",
        "stop_reason": None,
    }
