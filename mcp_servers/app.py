"""Shared FastMCP entry point for the five loan-copilot tool servers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loan_copilot.domain.authority import get_authority_matrix, lookup_authority
from loan_copilot.domain.borrowers import get_borrower_profile, search_borrowers
from loan_copilot.domain.covenants import evaluate_covenants, list_standard_covenants
from loan_copilot.domain.ratios import calculate_ratios, pro_forma_debt_service
from loan_copilot.memory import redis_store

def test_covenants(ratios: dict, covenants: list | None = None, label: str = "current") -> list:
    """Test one set of ratios against the standard covenants."""
    return evaluate_covenants(ratios, covenants, label)


PORTS = {
    "borrower": 8101,
    "financials": 8102,
    "covenants": 8103,
    "workflow": 8104,
    "approval": 8105,
}


def build(name: str):
    """Create one MCP server with its tools registered."""
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer(name)
    if name == "borrower":
        mcp.tool()(get_borrower_profile)
        mcp.tool()(search_borrowers)
    elif name == "financials":
        mcp.tool()(calculate_ratios)
        mcp.tool()(pro_forma_debt_service)
    elif name == "covenants":
        mcp.tool()(list_standard_covenants)
        mcp.tool()(test_covenants)
    elif name == "workflow":
        mcp.tool()(redis_store.create_case)
        mcp.tool()(redis_store.update_status)
        mcp.tool()(redis_store.get_case_status)
        mcp.tool()(redis_store.get_audit_trail)
    elif name == "approval":
        mcp.tool()(get_authority_matrix)
        mcp.tool()(lookup_authority)
        mcp.tool()(redis_store.record_hitl_decision)
        mcp.tool()(redis_store.record_final_decision)
        mcp.tool()(redis_store.get_decision)
    else:
        raise SystemExit(f"Unknown server {name}")
    return mcp


def serve(name: str) -> None:
    """Expose one server over streamable HTTP."""
    build(name).run(transport="streamable-http", host="127.0.0.1", port=PORTS[name])
