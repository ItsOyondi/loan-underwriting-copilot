"""Ping Azure Redis with the Entra ID credential from the signed-in Azure CLI user.

The rest of the suite clears REDIS_URL so it can run offline. This file reads
the project .env for the host check. The ping runs when LOAN_COPILOT_LIVE=1.
"""

from pathlib import Path

import pytest

from loan_copilot.config import ROOT, settings
from loan_copilot.memory.redis_store import _endpoint, ping_redis


def _configured_redis_url() -> str:
    env_file = Path(ROOT, ".env")
    if not env_file.is_file():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("REDIS_URL="):
            return line.split("=", 1)[1].strip()
    return ""


def test_azure_redis_url_uses_entra_id():
    url = _configured_redis_url()
    if not url:
        pytest.skip(".env is not in this checkout, so the Redis host cannot be checked.")
    host, port, use_entra = _endpoint(url)
    assert host == "redis-db-rs.eastus.redis.azure.net"
    assert port == 10000
    assert use_entra is True


def test_entra_redis_ping():
    if not settings.redis_url:
        pytest.skip("REDIS_URL is cleared for the offline suite. Set LOAN_COPILOT_LIVE=1 to ping.")
    assert ping_redis() is True
