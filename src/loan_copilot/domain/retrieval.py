"""Policy and precedent search. Local files are the offline index."""

from __future__ import annotations

import json
import re
from pathlib import Path

from loan_copilot.config import DATA, settings

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _load_folder(folder: Path) -> list[dict]:
    documents = []
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = _JSON_BLOCK.search(text)
        meta = json.loads(match.group(1)) if match else {}
        title = text.splitlines()[0].lstrip("# ").strip() if text.startswith("#") else path.stem
        documents.append(
            {
                "id": path.stem,
                "title": title,
                "content": text,
                "source_file": path.name,
                **meta,
            }
        )
    return documents


def _score(query: str, document: dict) -> int:
    words = [word.lower() for word in re.findall(r"[a-zA-Z0-9/]+", query) if len(word) > 2]
    haystack = f"{document.get('title', '')}\n{document.get('content', '')}".lower()
    return sum(1 for word in words if word in haystack)


def _search_local(folder: Path, query: str, limit: int, industry: str | None = None) -> list[dict]:
    documents = _load_folder(folder)
    if industry:
        narrowed = [doc for doc in documents if doc.get("industry", "").lower() == industry.lower()]
        documents = narrowed or documents
    ranked = sorted(documents, key=lambda doc: _score(query, doc), reverse=True)
    hits = []
    for document in ranked[:limit]:
        hits.append(
            {
                "id": document["id"],
                "title": document["title"],
                "source_file": document["source_file"],
                "industry": document.get("industry"),
                "excerpt": document["content"][:500],
            }
        )
    return hits


def _search_azure(index_name: str, query: str, limit: int, industry: str | None = None) -> list[dict] | None:
    if not settings.use_azure_search or not settings.azure_search_endpoint or not settings.azure_search_api_key:
        return None
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    client = SearchClient(settings.azure_search_endpoint, index_name, AzureKeyCredential(settings.azure_search_api_key))
    filter_text = f"industry eq '{industry}'" if industry else None
    results = client.search(search_text=query, top=limit, filter=filter_text)
    hits = []
    for item in results:
        hits.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "source_file": item.get("source_file"),
                "industry": item.get("industry"),
                "excerpt": (item.get("content") or "")[:500],
            }
        )
    return hits


def search_policy(query: str, limit: int = 3) -> list[dict]:
    """Find credit-policy passages for a query."""
    try:
        azure_hits = _search_azure(settings.azure_search_index_policies, query, limit)
    except Exception:
        azure_hits = None
    if azure_hits:
        return azure_hits
    return _search_local(DATA / "policies", query, limit)


def search_precedents(query: str, industry: str | None = None, limit: int = 3) -> list[dict]:
    """Find similar case summaries, preferring the same industry."""
    try:
        azure_hits = _search_azure(settings.azure_search_index_precedents, query, limit, industry)
    except Exception:
        azure_hits = None
    if azure_hits:
        return azure_hits
    return _search_local(DATA / "precedents", query, limit, industry)
