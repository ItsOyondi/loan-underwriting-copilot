"""Small HTTP API so a case can be started and approved without the CLI."""

from __future__ import annotations

from pydantic import BaseModel

from loan_copilot.resilience import breaker_state
from loan_copilot.service import current_view, resume_case, run_to_end, start_case

try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # pragma: no cover
    FastAPI = None


class StartRequest(BaseModel):
    sample_case: str
    case_id: str | None = None
    auto_approve: bool = False


class DecisionRequest(BaseModel):
    action: str
    comments: str = ""


def create_app():
    app = FastAPI(title="Loan underwriting copilot")

    @app.get("/health")
    def health():
        return {"status": "ok", "azure_openai_breaker": breaker_state("azure-openai")}

    @app.post("/cases")
    def create_case(body: StartRequest):
        case_id = body.case_id or body.sample_case
        try:
            if body.auto_approve:
                return run_to_end(case_id, body.sample_case)
            return start_case(case_id, body.sample_case)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/cases/{case_id}")
    def read_case(case_id: str):
        view = current_view(case_id)
        if not view.get("status") and not view.get("pending"):
            raise HTTPException(status_code=404, detail="Case not found")
        return view

    @app.get("/cases/{case_id}/pending")
    def read_pending(case_id: str):
        return {"case_id": case_id, "pending": current_view(case_id).get("pending")}

    @app.post("/cases/{case_id}/decisions")
    def decide(case_id: str, body: DecisionRequest):
        return resume_case(case_id, body.action, body.comments)

    @app.get("/cases/{case_id}/memo")
    def read_memo(case_id: str):
        memo = (current_view(case_id).get("memo") or {}).get("markdown", "")
        return {"case_id": case_id, "markdown": memo}

    @app.get("/cases/{case_id}/audit")
    def read_audit(case_id: str):
        return {"case_id": case_id, "audit": current_view(case_id).get("audit_log", [])}

    return app


app = create_app() if FastAPI else None
