"""Redis-backed rate limiting for the costly LLM endpoints.

A fixed window per identity (session id, else client IP) keeps one chat from
draining the plan/search budget. The limiter is deliberately fail-open: a
Redis outage must degrade to "no limiting", never to a broken assistant.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from ..errors import RateLimited
from .config import Settings, settings as default_settings

log = logging.getLogger(__name__)

WINDOW_S = 60
SCOPES = ("query", "plan")
# sanitize() fills this placeholder when the client sent no session; using
# it as a bucket key would put every anonymous visitor in one quota.
ANONYMOUS_SESSION = "anonymous"


class RateLimitStore(Protocol):
    async def incr(self, key: str, window_s: int) -> int: ...

    async def close(self) -> None: ...


class RedisRateLimitStore:
    """INCR + EXPIRE fixed window; 0 means "Redis unavailable, allow"."""

    def __init__(self, url: str, *, prefix: str = "assistant:rate:") -> None:
        from redis.asyncio import Redis

        self._client = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix
        self._warned = False

    async def incr(self, key: str, window_s: int) -> int:
        full_key = self._prefix + key
        try:
            count = int(await self._client.incr(full_key))
            if count == 1:
                # Only the first hit of a window arms the expiry, so a burst
                # cannot keep extending the window.
                await self._client.expire(full_key, max(1, int(window_s)))
            return count
        except Exception as exc:  # noqa: BLE001 — fail open by design
            if not self._warned:
                log.warning("rate limit store unavailable, allowing: %s", exc)
                self._warned = True
            return 0

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:  # noqa: BLE001
            pass


class InMemoryRateLimitStore:
    """Test double for the Redis store (never used in production wiring)."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[float, int]] = {}

    async def incr(self, key: str, window_s: int) -> int:
        now = time.monotonic()
        started, count = self._windows.get(key, (now, 0))
        if now - started >= window_s:
            started, count = now, 0
        count += 1
        self._windows[key] = (started, count)
        return count

    async def close(self) -> None:
        self._windows.clear()


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_s: int


class RateLimiter:
    def __init__(self, store: RateLimitStore, *, settings: Settings,
                 window_s: int = WINDOW_S) -> None:
        self._store = store
        self._settings = settings
        self._window_s = max(1, int(window_s))
        self._limits = {
            "query": max(0, int(settings.rate_limit_query_per_min)),
            "plan": max(0, int(settings.rate_limit_plan_per_min)),
        }
        self._warned = False

    async def check(self, scope: str, identity: str) -> RateLimitDecision:
        limit = self._limits.get(scope, 0)
        if not self._settings.rate_limit_enabled or limit <= 0:
            return RateLimitDecision(True, limit, limit, 0)
        try:
            count = await self._store.incr(f"{scope}:{identity}",
                                           self._window_s)
        except Exception as exc:  # noqa: BLE001 — fail open by design
            if not self._warned:
                log.warning("rate limit store failed, allowing: %s", exc)
                self._warned = True
            return RateLimitDecision(True, limit, limit, 0)
        if count <= 0:
            # Store failure: allow, exactly like the old unlimited behaviour.
            return RateLimitDecision(True, limit, limit, 0)
        if count > limit:
            return RateLimitDecision(False, limit, 0, self._window_s)
        return RateLimitDecision(True, limit, max(0, limit - count), 0)

    async def close(self) -> None:
        await self._store.close()


def _body_session_id(payload: dict) -> str | None:
    """Session id from a query turn or from a plan turn's contract."""
    candidates = [payload.get("session_id")]
    contract = payload.get("contract")
    if isinstance(contract, dict):
        context = contract.get("context_state")
        if isinstance(context, dict):
            candidates.append(context.get("session_id"))
    for value in candidates:
        if isinstance(value, str) and value.strip():
            text = value.strip()
            if text.casefold() != ANONYMOUS_SESSION:
                return text
    return None


async def client_identity(request: Request) -> str:
    """Session id from the JSON body, else the client IP (namespaced)."""
    session_id = None
    try:
        raw = await request.body()
        if raw:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                session_id = _body_session_id(payload)
    except (ValueError, UnicodeDecodeError):
        session_id = None
    if session_id:
        return f"session:{session_id}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def build_limiter(config: Settings) -> RateLimiter:
    return RateLimiter(RedisRateLimitStore(config.redis_url), settings=config)


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Process-wide limiter, built lazily so tests can inject a fake store."""
    global _limiter
    if _limiter is None:
        _limiter = build_limiter(default_settings)
    return _limiter


def set_limiter(limiter: RateLimiter | None) -> None:
    global _limiter
    _limiter = limiter


async def close_limiter() -> None:
    global _limiter
    if _limiter is not None:
        await _limiter.close()
        _limiter = None


def rate_limit(scope: str):
    """FastAPI dependency: 429 + Retry-After once the window quota is spent."""
    if scope not in SCOPES:
        raise ValueError(f"unknown rate limit scope {scope!r}")

    async def dependency(request: Request) -> None:
        decision = await get_limiter().check(
            scope, await client_identity(request))
        if not decision.allowed:
            raise RateLimited(
                f"Rate limit of {decision.limit} requests per "
                f"{decision.retry_after_s} s exceeded",
                retry_after_s=decision.retry_after_s)

    return dependency
