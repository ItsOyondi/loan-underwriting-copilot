"""Small helpers shared by the agent nodes."""

from __future__ import annotations

from loan_copilot.memory import redis_store


def audit(case_id: str, stage: str, status: str, note: str, borrower_id: str = "") -> dict:
    redis_store.update_status(case_id, stage, status, note, borrower_id=borrower_id)
    return {"stage": stage, "status": status, "note": note}
