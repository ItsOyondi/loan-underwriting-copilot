"""Azure AI Search helpers. Ingestion is optional; queries fall back to local files."""

from __future__ import annotations

from loan_copilot.domain.retrieval import search_policy, search_precedents

__all__ = ["search_policy", "search_precedents", "azure_configured"]


def azure_configured() -> bool:
    from loan_copilot.config import settings

    return bool(settings.use_azure_search and settings.azure_search_endpoint and settings.azure_search_api_key)
