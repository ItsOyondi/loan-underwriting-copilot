"""Load data/borrowers.json into Cosmos when USE_COSMOS and the account settings are set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loan_copilot.config import DATA, settings


def main() -> None:
    if not settings.cosmos_endpoint or not settings.cosmos_key:
        print("COSMOS_ENDPOINT or COSMOS_KEY is empty. The case runner will use data/borrowers.json.")
        return
    from azure.cosmos import CosmosClient, PartitionKey

    records = json.loads((DATA / "borrowers.json").read_text(encoding="utf-8"))
    client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
    database = client.create_database_if_not_exists(settings.cosmos_database)
    container = database.create_container_if_not_exists(
        settings.cosmos_container_customers,
        partition_key=PartitionKey(path="/borrowerId"),
    )
    for record in records:
        container.upsert_item(record)
    print(f"Upserted {len(records)} customers into {settings.cosmos_database}/{settings.cosmos_container_customers}")


if __name__ == "__main__":
    main()
