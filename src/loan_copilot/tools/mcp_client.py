"""Names of the five MCP servers. The local graph calls the Python functions directly.

Start a server with `python scripts/run_mcp.py borrower` when you want a remote tool endpoint.
"""

from __future__ import annotations

SERVERS = {
    "borrower": 8101,
    "financials": 8102,
    "covenants": 8103,
    "workflow": 8104,
    "approval": 8105,
}
