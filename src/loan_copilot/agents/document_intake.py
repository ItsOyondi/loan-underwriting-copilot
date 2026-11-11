"""Classify the four documents and attach the Cosmos or file customer record."""

from __future__ import annotations

from loan_copilot.agents.common import audit
from loan_copilot.domain.borrowers import UnknownCustomerError, get_borrower_profile
from loan_copilot.domain.documents import load_case
from loan_copilot.llm import complete
from loan_copilot.schemas import IntakeResult


def document_intake(state: dict) -> dict:
    case_id = state["case_id"]
    documents, missing = load_case(state["case_dir"])
    if missing:
        note = "Missing documents: " + ", ".join(missing)
        return {
            "stop_reason": "MISSING_DOCUMENTS",
            "status": "failed",
            "errors": [{"agent": "document_intake", "message": note}],
            "audit_log": [audit(case_id, "intake", "failed", note)],
        }

    request = documents["borrower_request.md"]
    financials = documents["financial_statements.md"]
    credit = documents["credit_report.md"]
    management = documents["management_report.md"]
    borrower_id = request["borrower_id"]
    try:
        customer = get_borrower_profile(borrower_id)
    except UnknownCustomerError:
        note = f"Unknown customer {borrower_id}"
        return {
            "stop_reason": "UNKNOWN_CUSTOMER",
            "status": "failed",
            "errors": [{"agent": "document_intake", "message": note}],
            "audit_log": [audit(case_id, "intake", "failed", note)],
        }

    legal_name = customer["legalName"]
    name_matches = request["borrower_name"].strip().lower() == legal_name.strip().lower()
    offline = IntakeResult(
        borrower_id=borrower_id,
        borrower_name=request["borrower_name"],
        legal_name=legal_name,
        industry=customer.get("industry", ""),
        requested_amount=request["requested_amount"],
        tenor_years=request["tenor_years"],
        purpose=request["purpose"],
        collateral=request["collateral"],
        bureau_score=int(credit.get("bureau_score", 0)),
        years=financials["years"],
        facilities=customer.get("facilities", []),
        related_parties=customer.get("relatedParties", []),
        name_matches_customer=name_matches,
        management_excerpt=management["text"][:400],
        summary=(
            f"{legal_name} requests ${request['requested_amount']:,.0f} for {request['purpose']}. "
            f"Customer record {borrower_id} is {customer.get('kycStatus', 'on file')}."
        ),
    )
    model = complete(
        "mini",
        IntakeResult,
        "Summarize the loan request in the summary field. Keep every number from the user message.",
        offline.model_dump_json(),
    )
    result = offline if model is None else offline.model_copy(update={"summary": model.summary or offline.summary})
    return {
        "intake": result.model_dump(),
        "status": "analysis",
        "stop_reason": None,
        "audit_log": [audit(case_id, "intake", "complete", result.summary, borrower_id)],
    }
