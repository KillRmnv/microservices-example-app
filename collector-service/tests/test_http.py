import asyncio

import httpx
import pytest

from app.http import PoliteClient


def make_client(**kwargs) -> PoliteClient:
    return PoliteClient(user_agent="test/0.1", **kwargs)


@pytest.mark.asyncio
async def test_get_returns_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    client = make_client(transport=httpx.MockTransport(handler))
    response = await client.get("probe", "https://example.com/")
    assert response.status_code == 200
    assert response.text == "ok"
    await client.aclose()


@pytest.mark.asyncio
async def test_retries_then_raises():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(503, text="busy")

    client = make_client(
        transport=httpx.MockTransport(handler), max_attempts=3, backoff_base_s=0.001
    )
    with pytest.raises(RuntimeError):
        await client.get("probe", "https://example.com/")
    assert len(calls) == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_paces_requests():
    times = []

    def handler(request: httpx.Request) -> httpx.Response:
        times.append(asyncio.get_event_loop().time())
        return httpx.Response(200, text="ok")

    client = make_client(transport=httpx.MockTransport(handler), default_min_interval_s=0.2)
    await client.get("probe", "https://example.com/a")
    await client.get("probe", "https://example.com/b")
    assert times[1] - times[0] >= 0.15
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_after_is_honoured():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(asyncio.get_event_loop().time())
        if len(seen) == 1:
            return httpx.Response(429, text="slow", headers={"retry-after": "1"})
        return httpx.Response(200, text="ok")

    client = make_client(transport=httpx.MockTransport(handler), backoff_base_s=0.001)
    response = await client.get("probe", "https://example.com/")
    assert response.status_code == 200
    assert seen[1] - seen[0] >= 0.9
    await client.aclose()


@pytest.mark.asyncio
async def test_before_attempt_runs_per_http_attempt():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="busy")

    client = make_client(transport=httpx.MockTransport(handler),
                         max_attempts=3, backoff_base_s=0.001)
    with pytest.raises(RuntimeError):
        await client.get("probe", "https://example.com/",
                         before_attempt=lambda: attempts.append(1))
    assert len(attempts) == 3
    await client.aclose()
