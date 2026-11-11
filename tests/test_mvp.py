"""Offline checks for the ratios, covenants, authority matrix, and the case graph."""

from __future__ import annotations

import shutil

from langgraph.checkpoint.memory import MemorySaver

from loan_copilot.agents.document_intake import document_intake
from loan_copilot.config import DATA, settings
from loan_copilot.domain.authority import lookup_authority
from loan_copilot.domain.covenants import evaluate_covenants
from loan_copilot.domain.documents import load_case
from loan_copilot.domain.ratios import calculate_ratios
from loan_copilot.domain.retrieval import search_policy, search_precedents
from loan_copilot.graph import build_graph
from loan_copilot.resilience import CircuitOpenError, MaxRetriesExceeded, reset_breakers, resilient_call
from loan_copilot.service import execute
from loan_copilot.tools.local_tools import search_policy as search_policy_tool


def _years(case_name: str) -> list[dict]:
    documents, missing = load_case(DATA / "sample_cases" / case_name)
    assert not missing
    return documents["financial_statements.md"]["years"]


def test_strong_case_ratios_clear_the_policy_floor():
    latest = calculate_ratios(_years("case_001_strong"))[-1]
    assert latest["dscr"] == 2.4
    assert latest["debt_to_ebitda"] == 2.5
    assert latest["revenue_growth"] == 0.2
    assert all(row["passed"] for row in evaluate_covenants(latest))


def test_breach_case_fails_the_standard_covenants():
    latest = calculate_ratios(_years("case_003_breach"))[-1]
    failed = [row["name"] for row in evaluate_covenants(latest) if not row["passed"]]
    assert failed == [
        "Minimum DSCR",
        "Maximum Debt/EBITDA",
        "Minimum current ratio",
        "Minimum interest coverage",
    ]


def test_authority_matrix_matches_the_sample_bands():
    assert lookup_authority(1_000_000, 3) == "Credit Officer"
    assert lookup_authority(1_500_000, 3) == "Senior Credit Officer"
    assert lookup_authority(4_000_000, 6) == "Credit Committee"
    assert lookup_authority(2_000_000, 8) == "Credit Committee"
    assert lookup_authority(30_000_000, 2) == "Board Credit Committee"


def test_policy_search_finds_the_dscr_rule():
    hits = search_policy("minimum DSCR covenant")
    assert hits
    assert any("1.25" in hit["excerpt"] for hit in hits)
    precedents = search_precedents("equipment loan", industry="Manufacturing")
    assert precedents[0]["industry"] == "Manufacturing"
    assert "DSCR" in search_policy_tool.invoke({"query": "DSCR"})


def test_missing_document_stops_intake(tmp_path):
    dest = tmp_path / "partial"
    shutil.copytree(DATA / "sample_cases" / "case_001_strong", dest)
    (dest / "credit_report.md").unlink()
    result = document_intake({"case_id": "missing-doc", "case_dir": str(dest)})
    assert result["stop_reason"] == "MISSING_DOCUMENTS"


def test_unknown_customer_stops_intake(tmp_path):
    dest = tmp_path / "unknown"
    shutil.copytree(DATA / "sample_cases" / "case_001_strong", dest)
    request = dest / "borrower_request.md"
    request.write_text(
        request.read_text(encoding="utf-8").replace("BRW-1008", "BRW-MISSING"),
        encoding="utf-8",
    )
    result = document_intake({"case_id": "unknown", "case_dir": str(dest)})
    assert result["stop_reason"] == "UNKNOWN_CUSTOMER"


def test_case_graph_approves_the_strong_file_and_declines_inside_the_breach_file():
    graph = build_graph(MemorySaver())
    strong = execute(graph, "case-strong", "case_001_strong")
    assert strong["status"] == "approved"
    assert strong["risk"]["recommendation"] == "approve"
    assert strong["risk"]["risk_grade"] == 3
    assert strong["route"]["approver_level"] == "Senior Credit Officer"
    assert "Northwind Packaging" in strong["memo"]["markdown"]
    assert len(strong["hitl_decisions"]) == 3

    breach = execute(graph, "case-breach", "case_003_breach")
    assert breach["risk"]["recommendation"] == "decline"
    assert breach["covenants"]["breaches"]
    assert breach["status"] == "approved"

    borderline = execute(graph, "case-border", "case_002_borderline")
    assert borderline["risk"]["recommendation"] == "approve_with_conditions"
    assert borderline["route"]["approver_level"] == "Credit Committee"


def test_reviewer_can_reject_at_the_first_checkpoint():
    graph = build_graph(MemorySaver())
    rejected = execute(graph, "case-reject", "case_001_strong", actions=["reject"])
    assert rejected["status"] == "rejected"
    assert rejected["memo"] is None


def test_breaker_opens_after_repeated_failures(monkeypatch):
    monkeypatch.setattr("loan_copilot.resilience.time.sleep", lambda _seconds: None)
    original = (settings.max_retries, settings.cb_failure_threshold)
    settings.max_retries = 1
    settings.cb_failure_threshold = 2
    reset_breakers()

    def fail():
        raise RuntimeError("dependency down")

    try:
        for _ in range(2):
            try:
                resilient_call("unit-demo", fail)
            except MaxRetriesExceeded:
                pass
        try:
            resilient_call("unit-demo", fail)
            raised = False
        except CircuitOpenError:
            raised = True
        assert raised
    finally:
        settings.max_retries, settings.cb_failure_threshold = original
        reset_breakers()
