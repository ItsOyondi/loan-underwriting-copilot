"""Ping Azure Redis with Entra ID and read back one short-lived key.

Reads REDIS_URL from the finUseCase .env file. A value with no password,
including host:10000, connects with TLS and DefaultAzureCredential.
Sign in first with `az login`. No secret is printed.

    .\.venv\Scripts\python scripts\test_redis.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def endpoint(url: str) -> tuple[str, int]:
    """Return the TLS host and port. host:10000 is treated as rediss."""
    raw = url.strip()
    if "://" not in raw:
        raw = f"rediss://{raw}"
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise SystemExit("REDIS_URL has no host.")
    port = parsed.port or 10000
    return parsed.hostname, port


def main() -> int:
    import redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    from redis_entraid.cred_provider import create_from_default_azure_credential

    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        print("REDIS_URL is empty.")
        return 1
    host, port = endpoint(url)
    print(f"Connecting to {host}:{port} with Entra ID")
    provider = create_from_default_azure_credential(("https://redis.azure.com/.default",))
    client = redis.Redis(
        host=host,
        port=port,
        ssl=True,
        credential_provider=provider,
        decode_responses=True,
        socket_connect_timeout=8,
        retry=Retry(NoBackoff(), 1),
    )
    try:
        print("PING", client.ping())
        client.set("loan-copilot:entra-test", "ok", ex=60)
        print("READ", client.get("loan-copilot:entra-test"))
    except Exception as exc:
        print(f"Redis test failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        client.close()
    print("Redis Entra ID test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
