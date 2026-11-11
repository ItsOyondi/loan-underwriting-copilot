"""Retries, a retry ceiling, and a circuit breaker around external calls."""

from __future__ import annotations

import time
from loan_copilot.config import settings


class CircuitOpenError(RuntimeError):
    """The breaker is open, so the call was not attempted."""


class MaxRetriesExceeded(RuntimeError):
    """The call failed on every allowed attempt."""


class _Breaker:
    def __init__(self, name: str) -> None:
        self.name = name
        self.failures: list[float] = []
        self.open_until = 0.0

    def allow(self) -> bool:
        now = time.monotonic()
        if self.open_until and now < self.open_until:
            return False
        if self.open_until and now >= self.open_until:
            self.open_until = 0.0
        window_start = now - settings.cb_window_seconds
        self.failures = [stamp for stamp in self.failures if stamp >= window_start]
        return True

    def success(self) -> None:
        self.failures.clear()
        self.open_until = 0.0

    def failure(self) -> None:
        now = time.monotonic()
        self.failures.append(now)
        window_start = now - settings.cb_window_seconds
        recent = [stamp for stamp in self.failures if stamp >= window_start]
        self.failures = recent
        if len(recent) >= settings.cb_failure_threshold:
            self.open_until = now + settings.cb_cooldown_seconds

    @property
    def state(self) -> str:
        if self.open_until and time.monotonic() < self.open_until:
            return "open"
        return "closed"


_BREAKERS: dict[str, _Breaker] = {}


def _breaker(name: str) -> _Breaker:
    if name not in _BREAKERS:
        _BREAKERS[name] = _Breaker(name)
    return _BREAKERS[name]


def breaker_state(name: str) -> str:
    return _breaker(name).state


def reset_breakers() -> None:
    _BREAKERS.clear()


def resilient_call(name: str, func, *args, **kwargs):
    """Call `func` with backoff. Open the breaker after repeated failures."""
    breaker = _breaker(name)
    if not breaker.allow():
        raise CircuitOpenError(name)
    last_error: Exception | None = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            breaker.failure()
            if attempt == settings.max_retries or not breaker.allow():
                break
            time.sleep(min(2 ** (attempt - 1), 2))
            continue
        breaker.success()
        return result
    raise MaxRetriesExceeded(name) from last_error
