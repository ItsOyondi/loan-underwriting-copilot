"""Customer records. Cosmos is the store when enabled. The JSON file is the offline store."""

from __future__ import annotations

import json
import logging

from loan_copilot.config import DATA, settings

log = logging.getLogger(__name__)


class UnknownCustomerError(KeyError):
    """The borrower id is not in the customer store."""


def _records_from_file() -> list[dict]:
    return json.loads((DATA / "borrowers.json").read_text(encoding="utf-8"))


def _container():
    """Return the Cosmos customers container, or None when Cosmos is off or unreachable."""
    if not settings.use_cosmos or not settings.cosmos_endpoint or not settings.cosmos_key:
        return None
    try:
        from azure.cosmos import CosmosClient

        client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        database = client.get_database_client(settings.cosmos_database)
        return database.get_container_client(settings.cosmos_container_customers)
    except Exception as exc:
        log.warning("Cosmos customer store is unavailable. Using data/borrowers.json. %s", exc)
        return None


def _file_profile(borrower_id: str) -> dict:
    for record in _records_from_file():
        if record.get("borrowerId") == borrower_id or record.get("id") == borrower_id:
            return record
    raise UnknownCustomerError(borrower_id)


OWNER_MISSING_SUBSTATUS = 1003


def _owner_missing(exc: Exception) -> bool:
    """True when the database or container does not exist yet (not when the item is absent)."""
    if getattr(exc, "sub_status", None) == OWNER_MISSING_SUBSTATUS:
        return True
    return "Owner resource does not exist" in str(exc)


def get_borrower_profile(borrower_id: str) -> dict:
    """Point read of one customer, including facilities and related parties."""
    container = _container()
    if container is None:
        return _file_profile(borrower_id)
    try:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        return container.read_item(item=borrower_id, partition_key=borrower_id)
    except CosmosResourceNotFoundError as exc:
        if _owner_missing(exc):
            log.warning("Cosmos database or container is missing. Run scripts\\seed_cosmos.py. Using data/borrowers.json.")
            return _file_profile(borrower_id)
        raise UnknownCustomerError(borrower_id) from exc
    except Exception as exc:
        log.warning("Cosmos read for %s failed. Using data/borrowers.json. %s", borrower_id, exc)
        return _file_profile(borrower_id)


def search_borrowers(name: str) -> list[dict]:
    """Case-insensitive name search over the customer store."""
    container = _container()
    if container is not None:
        try:
            query = "SELECT * FROM c WHERE CONTAINS(c.legalName, @name, true)"
            return list(
                container.query_items(
                    query=query,
                    parameters=[{"name": "@name", "value": name}],
                    enable_cross_partition_query=True,
                )
            )
        except Exception as exc:
            log.warning("Cosmos name search failed. Using data/borrowers.json. %s", exc)
    needle = name.lower()
    return [record for record in _records_from_file() if needle in record.get("legalName", "").lower()]
