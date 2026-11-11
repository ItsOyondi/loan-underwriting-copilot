"""Case status, audit trail, and approval decisions.

Redis is used when REDIS_URL answers a ping. Otherwise the same records
are written to data/runtime/store.json so the MVP runs with no server.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from loan_copilot.config import RUNTIME, settings

_LOCK = threading.Lock()
_FILE = RUNTIME / "store.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict:
    return {"cases": {}, "decisions": {}}


def _read() -> dict:
    if not _FILE.is_file():
        return _empty()
    return json.loads(_FILE.read_text(encoding="utf-8"))


def _write(document: dict) -> None:
    _FILE.write_text(json.dumps(document, indent=2), encoding="utf-8")


_CLIENT = None
_CLIENT_READY = False
_LAST_ERROR: Exception | None = None


def _endpoint(url: str) -> tuple[str, int, bool]:
    """Return host, port, and whether to sign in with Entra ID.

    A rediss URL with no password, including `host:10000`, uses Entra ID.
    A redis URL with a password stays on that password.
    """
    raw = url.strip()
    if "://" not in raw:
        raw = f"rediss://{raw}"
    from urllib.parse import urlparse

    parsed = urlparse(raw)
    host = parsed.hostname or ""
    port = parsed.port or (10000 if parsed.scheme == "rediss" else 6379)
    use_entra = parsed.scheme == "rediss" and not parsed.password
    return host, port, use_entra


def _redis():
    """Return a live Redis client, or None when the server cannot be reached."""
    global _CLIENT, _CLIENT_READY, _LAST_ERROR
    if _CLIENT_READY:
        return _CLIENT
    _CLIENT_READY = True
    if not settings.redis_url:
        return None
    try:
        import redis

        host, port, use_entra = _endpoint(settings.redis_url)
        if use_entra:
            from redis_entraid.cred_provider import create_from_default_azure_credential

            from redis.backoff import NoBackoff
            from redis.retry import Retry

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
        else:
            client = redis.Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=0.5,
                decode_responses=True,
            )
        client.ping()
        _CLIENT = client
        _LAST_ERROR = None
        return client
    except Exception as exc:
        _LAST_ERROR = exc
        return None


def ping_redis() -> bool:
    """Ping Redis with the project client. Entra ID is used for Azure Redis."""
    global _CLIENT, _CLIENT_READY
    _CLIENT = None
    _CLIENT_READY = False
    client = _redis()
    if client is None:
        raise RuntimeError("Redis ping failed") from _LAST_ERROR
    return client.ping() is True


def create_case(case_id: str, borrower_id: str, note: str = "") -> dict:
    return update_status(case_id, "intake", "started", note, borrower_id=borrower_id)


def update_status(case_id: str, stage: str, status: str, note: str = "", borrower_id: str = "") -> dict:
    event = {"stage": stage, "status": status, "note": note, "at": _now()}
    client = _redis()
    if client is not None:
        key = f"case:{case_id}:audit"
        client.rpush(key, json.dumps(event))
        client.hset(
            f"case:{case_id}:status",
            mapping={"stage": stage, "status": status, "borrower_id": borrower_id, "updated_at": event["at"]},
        )
        return event
    with _LOCK:
        document = _read()
        case = document["cases"].setdefault(case_id, {"borrower_id": borrower_id, "events": []})
        if borrower_id:
            case["borrower_id"] = borrower_id
        case["stage"] = stage
        case["status"] = status
        case["events"].append(event)
        _write(document)
    return event


def get_case_status(case_id: str) -> dict:
    client = _redis()
    if client is not None:
        data = client.hgetall(f"case:{case_id}:status")
        return {
            key.decode() if isinstance(key, bytes) else key: value.decode() if isinstance(value, bytes) else value
            for key, value in data.items()
        }
    with _LOCK:
        case = _read()["cases"].get(case_id)
    if not case:
        return {}
    return {"stage": case.get("stage", ""), "status": case.get("status", ""), "borrower_id": case.get("borrower_id", "")}


def get_audit_trail(case_id: str) -> list[dict]:
    client = _redis()
    if client is not None:
        rows = client.lrange(f"case:{case_id}:audit", 0, -1)
        return [json.loads(row) for row in rows]
    with _LOCK:
        case = _read()["cases"].get(case_id, {})
    return list(case.get("events", []))


def record_hitl_decision(case_id: str, checkpoint: str, action: str, comments: str, reviewer: str = "cli") -> dict:
    decision = {
        "case_id": case_id,
        "checkpoint": checkpoint,
        "action": action,
        "comments": comments,
        "reviewer": reviewer,
        "at": _now(),
    }
    _save_decision(case_id, decision, final=False)
    return decision


def record_final_decision(case_id: str, action: str, comments: str, reviewer: str = "cli") -> dict:
    decision = {
        "case_id": case_id,
        "checkpoint": "final",
        "action": action,
        "comments": comments,
        "reviewer": reviewer,
        "at": _now(),
        "final": True,
    }
    _save_decision(case_id, decision, final=True)
    return decision


def get_decision(case_id: str) -> dict:
    client = _redis()
    if client is not None:
        raw = client.get(f"decision:{case_id}")
        return json.loads(raw) if raw else {}
    with _LOCK:
        return dict(_read()["decisions"].get(case_id, {}))


def _save_decision(case_id: str, decision: dict, final: bool) -> None:
    client = _redis()
    if client is not None:
        current = get_decision(case_id)
        history = current.get("history", [])
        history.append(decision)
        payload = {"history": history, "final": decision if final else current.get("final")}
        client.set(f"decision:{case_id}", json.dumps(payload))
        return
    with _LOCK:
        document = _read()
        current = document["decisions"].setdefault(case_id, {"history": [], "final": None})
        current["history"].append(decision)
        if final:
            current["final"] = decision
        _write(document)
