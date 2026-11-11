"""Ping Azure Redis with the Entra ID credential from the signed-in Azure CLI user.

The rest of the suite clears REDIS_URL so it can run offline. This file reads
the project .env for the host check. The ping runs when LOAN_COPILOT_LIVE=1.
"""

from pathlib import Path

import pytest

from loan_copilot.config import ROOT, settings
from loan_copilot.memory.redis_store import _endpoint, ping_redis


def _configured_redis_url() -> str:
    for line in Path(ROOT, ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("REDIS_URL="):
            return line.split("=", 1)[1].strip()
    return ""


def test_azure_redis_url_uses_entra_id():
    host, port, use_entra = _endpoint(_configured_redis_url())
    assert host == "redis-db-rs.eastus.redis.azure.net"
    assert port == 10000
    assert use_entra is True


def test_entra_redis_ping():
    if not settings.redis_url:
        pytest.skip("REDIS_URL is cleared for the offline suite. Set LOAN_COPILOT_LIVE=1 to ping.")
    assert ping_redis() is True
