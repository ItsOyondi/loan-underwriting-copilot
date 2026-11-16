"""Approval routes the model is allowed to call."""

from __future__ import annotations

from semantic_kernel.functions import kernel_function

PLUGIN_NAME = "ApprovalRoutes"

ROUTE_FUNCTIONS = (
    f"{PLUGIN_NAME}-credit_officer",
    f"{PLUGIN_NAME}-senior_credit_officer",
    f"{PLUGIN_NAME}-credit_committee",
    f"{PLUGIN_NAME}-board_credit_committee",
)


class ApprovalRoutes:
    """One function per approver. The model picks the function."""

    def __init__(self) -> None:
        self.chosen = ""

    def _queue(self, approver: str, case_summary: str) -> str:
        self.chosen = approver
        return f"Queued with {approver}: {case_summary}"

    @kernel_function(
        description=(
            "Route to a Credit Officer. Use only when the amount is at most "
            "$1,000,000 and the risk grade is 1 to 4."
        )
    )
    def credit_officer(self, case_summary: str) -> str:
        return self._queue("Credit Officer", case_summary)

    @kernel_function(
        description=(
            "Route to a Senior Credit Officer. Use when the amount is at most "
            "$1,000,000 and the risk grade is 5 or 6, or when the amount is "
            "above $1,000,000 and at most $5,000,000 and the risk grade is 1 to 4."
        )
    )
    def senior_credit_officer(self, case_summary: str) -> str:
        return self._queue("Senior Credit Officer", case_summary)

    @kernel_function(
        description=(
            "Route to the Credit Committee. Use when the amount is at most "
            "$5,000,000 and the risk grade is 7 or higher, or when the amount "
            "is above $5,000,000 and at most $25,000,000 and the risk grade is 1 to 6."
        )
    )
    def credit_committee(self, case_summary: str) -> str:
        return self._queue("Credit Committee", case_summary)

    @kernel_function(
        description=(
            "Route to the Board Credit Committee. Use when the amount is above "
            "$25,000,000, or when the amount is above $5,000,000 and the risk grade is 7 or higher."
        )
    )
    def board_credit_committee(self, case_summary: str) -> str:
        return self._queue("Board Credit Committee", case_summary)
