"""Approval Record MCP server. Decisions are stored for the case."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import serve

if __name__ == "__main__":
    serve("approval")
