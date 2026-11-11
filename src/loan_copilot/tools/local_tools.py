"""In-process tools the model can call. The graph also calls these functions directly."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from loan_copilot.domain.documents import parse_document
from loan_copilot.domain.retrieval import search_policy as search_policy_fn
from loan_copilot.domain.retrieval import search_precedents as search_precedents_fn


@tool
def parse_document_tool(path: str) -> str:
    """Read one case document and return its JSON facts and source name."""
    parsed = parse_document(path)
    parsed.pop("text", None)
    return json.dumps(parsed)


@tool
def search_policy(query: str) -> str:
    """Search credit policy text for clauses that match the query."""
    return json.dumps(search_policy_fn(query))


@tool
def search_precedents(query: str, industry: str = "") -> str:
    """Search approved and declined case summaries. Pass an industry to prefer that industry."""
    return json.dumps(search_precedents_fn(query, industry or None))


LOCAL_TOOLS = [parse_document_tool, search_policy, search_precedents]
