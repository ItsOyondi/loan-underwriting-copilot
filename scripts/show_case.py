"""Print one case from Azure Redis, or list the case ids stored there.

Uses Entra ID, the same sign-in as the case runner. Sign in with `az login` first.

    uv run scripts/show_case.py
    uv run scripts/show_case.py case_001_strong-cb656f36
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _client():
    import redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    from redis_entraid.cred_provider import create_from_default_azure_credential

    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        raise SystemExit("REDIS_URL is empty.")
    raw = url if "://" in url else f"rediss://{url}"
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise SystemExit("REDIS_URL has no host.")
    provider = create_from_default_azure_credential(("https://redis.azure.com/.default",))
    return redis.Redis(
        host=parsed.hostname,
        port=parsed.port or 10000,
        ssl=True,
        credential_provider=provider,
        decode_responses=True,
        socket_connect_timeout=8,
        retry=Retry(NoBackoff(), 1),
    )


def _matching_keys(client, prefix: str) -> list[str]:
    """Return every key with this prefix.

    SCAN on Azure Managed Redis intermittently returns an empty page with
    cursor 0 (the same call succeeds or fails from one connection to the
    next), so the listing uses KEYS, which returned all keys every time.
    The cache holds a small number of case keys, so KEYS is cheap here.
    """
    return list(client.keys(f"{prefix}*"))


def _case_ids(client) -> list[str]:
    found = set()
    for key in _matching_keys(client, "case:"):
        parts = key.split(":")
        if len(parts) >= 3:
            found.add(parts[1])
    for key in _matching_keys(client, "decision:"):
        found.add(key.split(":", 1)[1])
    return sorted(found)


def _show(client, case_id: str) -> None:
    status = client.hgetall(f"case:{case_id}:status")
    audit = [json.loads(row) for row in client.lrange(f"case:{case_id}:audit", 0, -1)]
    raw_decision = client.get(f"decision:{case_id}")
    decision = json.loads(raw_decision) if raw_decision else None
    if not status and not audit and decision is None:
        raise SystemExit(f"No Redis record for {case_id}.")
    print(f"Case {case_id}")
    print("Status")
    if status:
        for name in ("stage", "status", "borrower_id", "updated_at"):
            if status.get(name):
                print(f"  {name}: {status[name]}")
    else:
        print("  (none)")
    print("Audit")
    for event in audit:
        print(f"  {event.get('at', '')}  {event.get('stage', '')}  {event.get('status', '')}")
        note = (event.get("note") or "").strip()
        if note:
            print(f"    {note}")
    print("Decision")
    if not decision:
        print("  (none)")
        return
    final = decision.get("final") or {}
    if final:
        print(f"  final: {final.get('action', '')} at {final.get('at', '')}")
    for item in decision.get("history") or []:
        print(f"  {item.get('at', '')}  {item.get('checkpoint', '')}  {item.get('action', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a loan case stored in Redis.")
    parser.add_argument("case_id", nargs="?", help="Case id. Omit it to list every stored case.")
    args = parser.parse_args()
    client = _client()
    try:
        if not args.case_id:
            ids = _case_ids(client)
            if not ids:
                print("No cases in Redis.")
                return 0
            print("\n".join(ids))
            return 0
        _show(client, args.case_id)
        return 0
    except Exception as exc:
        print(f"Redis read failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
