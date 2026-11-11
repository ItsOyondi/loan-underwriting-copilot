"""Functional checks against the checked-in sample cases."""

from __future__ import annotations

import asyncio

from loan_copilot.graph import build_graph
from loan_copilot.memory import redis_store
from loan_copilot.samples import load_catalog, outcome_errors, validate_catalog
from loan_copilot.service import execute


def test_cosmos_secret_parser_keeps_the_account_key_separate():
    from loan_copilot.config import account_from_cosmos_secret

    endpoint, key = account_from_cosmos_secret(
        "AccountEndpoint=https://example.documents.azure.com:443/;AccountKey=old",
        "vault-key",
    )
    assert endpoint == "https://example.documents.azure.com:443/"
    assert key == "vault-key"
    endpoint, key = account_from_cosmos_secret("https://example.documents.azure.com:443/", "vault-key")
    assert endpoint == "https://example.documents.azure.com:443/"
    assert key == "vault-key"


def test_sample_catalog_matches_the_files_and_ratio_tools():
    errors = validate_catalog()
    assert errors == [], "\n".join(errors)


def test_each_sample_case_reaches_its_catalog_outcome():
    graph = build_graph()
    failures = []
    for case in load_catalog()["cases"]:
        view = execute(graph, f"pack-{case['id']}", case["id"])
        failures.extend(outcome_errors(view, case))
    assert failures == [], "\n".join(failures)


def test_reviewer_can_revise_decline_send_back_and_hit_the_revision_cap():
    graph = build_graph()

    revised = execute(
        graph,
        "pack-revise",
        "case_001_strong",
        ["revise", "approve", "approve", "approve"],
    )
    assert revised["status"] == "approved"
    assert "Reviewer feedback: mvp" in revised["risk"]["narrative"]
    assert len(revised["hitl_decisions"]) == 4

    declined = execute(
        graph,
        "pack-decline",
        "case_001_strong",
        ["approve", "approve", "decline"],
    )
    assert declined["status"] == "declined"
    assert declined["risk"]["recommendation"] == "approve"
    assert redis_store.get_decision("pack-decline")["final"]["action"] == "decline"

    sent_back = execute(
        graph,
        "pack-send-back",
        "case_005_credit_officer",
        ["approve", "approve", "send_back", "approve", "approve"],
    )
    assert sent_back["status"] == "approved"
    assert sent_back["route"]["approver_level"] == "Credit Officer"
    assert [item["action"] for item in sent_back["hitl_decisions"]] == [
        "approve",
        "approve",
        "send_back",
        "approve",
        "approve",
    ]

    capped = execute(graph, "pack-cap", "case_001_strong", ["revise", "revise", "revise", "revise"])
    assert capped["status"] == "failed"
    assert capped["stop_reason"] == "revision cap reached"


def test_http_api_runs_a_sample_case_and_records_a_decision():
    from fastapi.testclient import TestClient

    from loan_copilot.api.main import app

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    started = client.post("/cases", json={"sample_case": "case_005_credit_officer", "case_id": "api-bakery"})
    assert started.status_code == 200
    assert started.json()["pending"]["checkpoint"] == "risk_review"

    decided = client.post(
        "/cases/api-bakery/decisions",
        json={"action": "approve", "comments": "functional"},
    )
    assert decided.status_code == 200
    assert decided.json()["pending"]["checkpoint"] == "memo_review"

    finished = client.post(
        "/cases",
        json={"sample_case": "case_006_board", "case_id": "api-board", "auto_approve": True},
    )
    assert finished.status_code == 200
    body = finished.json()
    assert body["status"] == "approved"
    assert body["route"]["approver_level"] == "Board Credit Committee"
    memo = client.get("/cases/api-board/memo")
    assert "Summit Steel Holdings" in memo.json()["markdown"]
    audit = client.get("/cases/api-board/audit")
    assert any(item["stage"] == "intake" for item in audit.json()["audit"])


def test_mcp_servers_expose_the_sample_data_tools():
    from mcp_servers.app import build

    expected = {
        "borrower": {"get_borrower_profile", "search_borrowers"},
        "financials": {"calculate_ratios", "pro_forma_debt_service"},
        "covenants": {"list_standard_covenants", "test_covenants"},
        "workflow": {"create_case", "update_status", "get_case_status", "get_audit_trail"},
        "approval": {
            "get_authority_matrix",
            "lookup_authority",
            "record_hitl_decision",
            "record_final_decision",
            "get_decision",
        },
    }

    async def tool_names(server) -> set[str]:
        listed = await server.list_tools()
        return {tool.name for tool in listed}

    for name, wanted in expected.items():
        found = asyncio.run(tool_names(build(name)))
        assert wanted <= found

    async def borrower():
        return await build("borrower").call_tool("get_borrower_profile", {"borrower_id": "BRW-4100"})

    result = asyncio.run(borrower())
    payload = getattr(result, "structuredContent", None) or getattr(result, "content", None) or result
    assert "Maple Street Bakery LLC" in str(payload)

    async def authority():
        return await build("approval").call_tool(
            "lookup_authority",
            {"amount": 28000000, "risk_grade": 3},
        )

    route = asyncio.run(authority())
    assert "Board Credit Committee" in str(route)

    async def matrix():
        return await build("approval").call_tool("get_authority_matrix", {})

    bands = asyncio.run(matrix())
    assert "Credit Officer" in str(bands)
    assert "Board Credit Committee" in str(bands)
