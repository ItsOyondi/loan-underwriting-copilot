"""Start one MCP server: borrower, financials, covenants, workflow, or approval."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp_servers"))

from app import serve

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "borrower"
    serve(name)
