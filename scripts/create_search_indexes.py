"""Create the two Azure AI Search indexes and upload the local markdown.

Policies go to loan-policy-memory from data/policies.
Precedents go to loan-case-precedents from data/precedents.
Vectors use text-embedding-3-small (1,536 dimensions).

Sign in with `az login` first. This script reads the search admin key and the
OpenAI endpoint from Key Vault when those .env values are empty.

    .\.venv\Scripts\python scripts\create_search_indexes.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loan_copilot.config import DATA, settings

VECTOR_DIMENSIONS = 1536
VECTOR_PROFILE = "loan-hnsw-profile"
VECTOR_ALGORITHM = "loan-hnsw"
_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_POLICY_ID = re.compile(r"Policy ID:\s*(\S+)")


def _title(text: str, path: Path) -> str:
    if text.startswith("#"):
        return text.splitlines()[0].lstrip("# ").strip()
    return path.stem


def _vector_search():
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        VectorSearch,
        VectorSearchProfile,
    )

    return VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=VECTOR_ALGORITHM)],
        profiles=[VectorSearchProfile(name=VECTOR_PROFILE, algorithm_configuration_name=VECTOR_ALGORITHM)],
    )


def _vector_field():
    from azure.search.documents.indexes.models import SearchField, SearchFieldDataType

    return SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=VECTOR_DIMENSIONS,
        vector_search_profile_name=VECTOR_PROFILE,
    )


def _shared_fields() -> list:
    from azure.search.documents.indexes.models import SearchableField, SearchFieldDataType, SimpleField

    return [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="embedding_model", type=SearchFieldDataType.String, filterable=True),
        _vector_field(),
    ]


def policy_index(name: str):
    from azure.search.documents.indexes.models import SearchableField, SearchFieldDataType, SearchIndex, SimpleField

    fields = _shared_fields() + [
        SimpleField(name="policy_id", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="section", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="version", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="effective_date", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="topic", type=SearchFieldDataType.String, filterable=True),
    ]
    return SearchIndex(name=name, fields=fields, vector_search=_vector_search())


def precedent_index(name: str):
    from azure.search.documents.indexes.models import SearchFieldDataType, SearchIndex, SimpleField

    fields = _shared_fields() + [
        SimpleField(name="industry", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="amount_band", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="risk_grade", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="decision", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="decision_date", type=SearchFieldDataType.String, filterable=True),
    ]
    return SearchIndex(name=name, fields=fields, vector_search=_vector_search())


def _embed(text: str) -> list[float]:
    endpoint = settings.azure_openai_endpoint.rstrip("/")
    model = settings.azure_openai_deployment_embedding
    if "/openai/v1" in endpoint:
        from openai import OpenAI

        client = OpenAI(base_url=endpoint, api_key=settings.azure_openai_api_key)
    else:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    vector = client.embeddings.create(model=model, input=text).data[0].embedding
    if len(vector) != VECTOR_DIMENSIONS:
        raise RuntimeError(f"Expected {VECTOR_DIMENSIONS} embedding dimensions, got {len(vector)}.")
    return vector


def _policy_document(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title = _title(text, path)
    policy_id = _POLICY_ID.search(text)
    return {
        "id": path.stem,
        "title": title,
        "content": text,
        "source_file": path.name,
        "embedding_model": settings.azure_openai_deployment_embedding,
        "content_vector": _embed(text),
        "policy_id": policy_id.group(1) if policy_id else path.stem,
        "section": "policy",
        "version": "1",
        "effective_date": "",
        "topic": title,
    }


def _precedent_document(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = _JSON_BLOCK.search(text)
    meta = json.loads(match.group(1)) if match else {}
    return {
        "id": path.stem,
        "title": _title(text, path),
        "content": text,
        "source_file": path.name,
        "embedding_model": settings.azure_openai_deployment_embedding,
        "content_vector": _embed(text),
        "industry": meta.get("industry", ""),
        "amount_band": meta.get("amount_band", ""),
        "risk_grade": int(meta.get("risk_grade", 0)),
        "decision": meta.get("decision", ""),
        "decision_date": meta.get("decision_date", ""),
    }


def _require_settings() -> None:
    missing = []
    if not settings.azure_search_endpoint:
        missing.append("AZURE_SEARCH_ENDPOINT")
    if not settings.azure_search_api_key:
        missing.append("AZURE_SEARCH_API_KEY or Key Vault secret clinic-ss-api-key")
    if not settings.azure_ready:
        missing.append("Azure OpenAI endpoint and key")
    if missing:
        raise SystemExit("Cannot index yet. Missing: " + ", ".join(missing))


def _upload(index_name: str, documents: list[dict]) -> None:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient

    credential = AzureKeyCredential(settings.azure_search_api_key)
    index_client = SearchIndexClient(settings.azure_search_endpoint, credential)
    search_client = SearchClient(settings.azure_search_endpoint, index_name, credential)
    try:
        builder = policy_index if index_name == settings.azure_search_index_policies else precedent_index
        index_client.create_or_update_index(builder(index_name))
        results = search_client.upload_documents(documents)
        failed = [item.key for item in results if not item.succeeded]
        if failed:
            raise RuntimeError(f"Upload failed for {len(failed)} document(s). First key: {failed[0]}")
    finally:
        search_client.close()
        index_client.close()


def main() -> None:
    _require_settings()
    policies = [_policy_document(path) for path in sorted((DATA / "policies").glob("*.md"))]
    precedents = [_precedent_document(path) for path in sorted((DATA / "precedents").glob("*.md"))]
    _upload(settings.azure_search_index_policies, policies)
    _upload(settings.azure_search_index_precedents, precedents)
    print(f"{settings.azure_search_index_policies}: {len(policies)} policy document(s)")
    print(f"{settings.azure_search_index_precedents}: {len(precedents)} precedent document(s)")
    print(f"Service: {settings.azure_search_endpoint}")


if __name__ == "__main__":
    main()
