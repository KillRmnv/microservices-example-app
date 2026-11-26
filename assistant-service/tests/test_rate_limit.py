import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.rate_limit import (
    InMemoryRateLimitStore,
    RateLimiter,
    rate_limit,
    set_limiter,
)
from app.errors import RateLimited
from app.errors.handlers import register_exception_handlers


class BrokenStore:
    async def incr(self, key: str, window_s: int) -> int:
        raise RuntimeError("redis is down")

    async def close(self) -> None:
        pass


def make_limiter(**overrides) -> RateLimiter:
    values = {"rate_limit_query_per_min": 2,
              "rate_limit_plan_per_min": 1}
    values.update(overrides)
    return RateLimiter(InMemoryRateLimitStore(), settings=Settings(**values))


@pytest.fixture(autouse=True)
def _reset_limiter():
    yield
    set_limiter(None)


@pytest.mark.asyncio
async def test_limiter_allows_n_then_blocks():
    limiter = make_limiter()
    decisions = [await limiter.check("query", "session:a") for _ in range(3)]
    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert decisions[-1].limit == 2
    assert decisions[-1].retry_after_s == 60


@pytest.mark.asyncio
async def test_different_sessions_have_independent_buckets():
    limiter = make_limiter()
    assert (await limiter.check("query", "session:a")).allowed
    assert (await limiter.check("query", "session:a")).allowed
    assert not (await limiter.check("query", "session:a")).allowed
    assert (await limiter.check("query", "session:b")).allowed


@pytest.mark.asyncio
async def test_scopes_have_separate_quotas():
    limiter = make_limiter()
    assert (await limiter.check("plan", "session:a")).allowed
    assert not (await limiter.check("plan", "session:a")).allowed
    assert (await limiter.check("query", "session:a")).allowed


@pytest.mark.asyncio
async def test_store_failure_fails_open():
    limiter = RateLimiter(BrokenStore(),
                          settings=Settings(rate_limit_query_per_min=1))
    for _ in range(5):
        assert (await limiter.check("query", "session:a")).allowed


@pytest.mark.asyncio
async def test_disabled_limiter_never_blocks():
    limiter = make_limiter(rate_limit_enabled=False)
    for _ in range(5):
        assert (await limiter.check("query", "session:a")).allowed


def test_rate_limited_response_is_a_problem_with_retry_after():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/limited")
    async def limited():
        raise RateLimited(retry_after_s=42)

    response = TestClient(app).get("/limited")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
    assert response.headers["content-type"].startswith(
        "application/problem+json")
    body = response.json()
    assert body["code"] == "rate_limited"
    assert body["status"] == 429


def _limited_app(scope: str) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/turn", dependencies=[Depends(rate_limit(scope))])
    async def turn() -> dict:
        return {"ok": True}

    return app


def test_query_dependency_keys_on_body_session_id():
    set_limiter(make_limiter(rate_limit_query_per_min=1))
    client = TestClient(_limited_app("query"))
    assert client.post("/turn", json={"query": "джаз",
                                      "session_id": "s1"}).status_code == 200
    assert client.post("/turn", json={"query": "джаз",
                                      "session_id": "s2"}).status_code == 200
    blocked = client.post("/turn", json={"query": "джаз", "session_id": "s1"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"


def test_plan_dependency_uses_the_contract_session_id():
    set_limiter(make_limiter(rate_limit_plan_per_min=1))
    client = TestClient(_limited_app("plan"))
    body = {"contract": {"context_state": {"session_id": "p1"}},
            "contexts": []}
    assert client.post("/turn", json=body).status_code == 200
    blocked = client.post("/turn", json=body)
    assert blocked.status_code == 429


class TurnBody(BaseModel):
    query: str = ""
    session_id: str | None = None


def test_dependency_does_not_consume_the_request_body():
    """The dependency reads the body for identity; FastAPI must still parse it."""
    set_limiter(make_limiter(rate_limit_query_per_min=5))
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/echo", dependencies=[Depends(rate_limit("query"))])
    async def echo(body: TurnBody) -> dict:
        return {"query": body.query}

    response = TestClient(app).post(
        "/echo", json={"query": "джаз", "session_id": "s1"})
    assert response.status_code == 200
    assert response.json() == {"query": "джаз"}


def test_anonymous_session_falls_back_to_the_client_ip():
    set_limiter(make_limiter(rate_limit_plan_per_min=1))
    client = TestClient(_limited_app("plan"))
    body = {"contract": {"context_state": {"session_id": "anonymous"}}}
    assert client.post("/turn", json=body).status_code == 200
    # The same placeholder must not get a fresh bucket on every request.
    assert client.post("/turn", json=body).status_code == 429
