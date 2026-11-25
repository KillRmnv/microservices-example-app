import httpx
import pytest

from app.api import deps
from app.clients.llm import (
    FallbackProvider,
    LlamaCppProvider,
    MockProvider,
    OpenAICompatProvider,
    OpenRouterProvider,
    provider_for,
)
from app.clients.llm.base import LLMUnavailable
from app.clients.llm.registry import BreakerProvider
from app.core.config import Settings


def make_settings(**overrides) -> Settings:
    base = {
        "llm_local_base_url": "http://llama:8080/v1",
        "llm_local_model": "qwen3:8b",
        "llm_external_base_url": "https://api.example.com/v1",
        "llm_external_api_key": "secret",
        "llm_external_model": "ext-model",
        "llm_stages": "structure:local,plan:external,telegram:mock",
    }
    base.update(overrides)
    return Settings(**base)


def test_backend_for_stage_mapping():
    settings = make_settings()
    assert settings.backend_for("structure") == "local"
    assert settings.backend_for("plan") == "external"
    assert settings.backend_for("telegram") == "mock"
    assert settings.backend_for("unknown-stage") == "local"


def test_legacy_ollama_name_maps_to_local():
    settings = make_settings(llm_stages="structure:ollama")
    assert settings.backend_for("structure") == "local"


def test_provider_for_selects_backend():
    settings = make_settings()
    assert isinstance(provider_for("structure", settings), LlamaCppProvider)
    assert isinstance(provider_for("plan", settings), OpenAICompatProvider)
    assert isinstance(provider_for("telegram", settings), MockProvider)


@pytest.mark.asyncio
async def test_openrouter_provider_sends_attribution_headers():
    settings = make_settings(
        llm_stages="structure:openrouter",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_key="or-secret",
        openrouter_model="z-ai/glm-5.3-flash",
        openrouter_referer="http://localhost:3000",
        openrouter_title="Dosug Assistant",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer or-secret"
        assert request.headers["HTTP-Referer"] == "http://localhost:3000"
        assert request.headers["X-Title"] == "Dosug Assistant"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{\"ok\": true}"}}]})

    provider = provider_for("structure", settings,
                            transport=httpx.MockTransport(handler))
    assert isinstance(provider, OpenRouterProvider)
    result = await provider.complete(system="s", user="u", json_mode=True,
                                     max_tokens=16)
    assert result == "{\"ok\": true}"


def test_thinking_override_switches_no_think_mode():
    settings = make_settings()
    fast = provider_for("structure", settings, thinking=False)
    assert isinstance(fast, LlamaCppProvider)
    payload = fast.payload(system="s", user="u", json_mode=True, max_tokens=64)
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    reasoning = provider_for("plan", settings, thinking=True)
    assert isinstance(reasoning, OpenAICompatProvider)
    local_reasoning = provider_for("structure", make_settings(), thinking=True)
    assert "chat_template_kwargs" not in local_reasoning.payload(
        system="s", user="u", json_mode=True, max_tokens=64)


def test_llama_payload_shape():
    provider = LlamaCppProvider("http://llama:8080/v1", "qwen3:8b", 5.0)
    payload = provider.payload(system="sys", user="hi", json_mode=False,
                               max_tokens=64)
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False
    assert payload["max_tokens"] == 64


def test_openai_payload_json_mode():
    provider = OpenAICompatProvider("https://api.example.com/v1", "m", "k", 5.0)
    payload = provider.payload(system="sys", user="hi", json_mode=True,
                               max_tokens=64)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0] == {"role": "system", "content": "sys"}


@pytest.mark.asyncio
async def test_llama_complete_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{\"a\": 1}"}}]})

    provider = LlamaCppProvider("http://llama:8080/v1", "qwen3:8b", 5.0,
                                transport=httpx.MockTransport(handler))
    text = await provider.complete(system="sys", user="hi", json_mode=True)
    assert text == "{\"a\": 1}"


@pytest.mark.asyncio
async def test_openai_complete_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "done"}}]})

    provider = OpenAICompatProvider("https://api.example.com/v1", "m", "secret",
                                    5.0, transport=httpx.MockTransport(handler))
    text = await provider.complete(system="sys", user="hi")
    assert text == "done"


@pytest.mark.asyncio
async def test_fallback_tries_next_provider_on_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "llama" in str(request.url):
            return httpx.Response(500, text="down")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "from external"}}]})

    settings = make_settings(llm_fallback_enabled=True,
                             llm_stages="plan:local")
    provider = provider_for("plan", settings,
                            transport=httpx.MockTransport(handler))
    assert isinstance(provider, FallbackProvider)
    assert provider.name == "fallback(local->external)"
    assert await provider.complete(system="s", user="u") == "from external"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_mock_provider_returns_valid_fragment():
    import json

    from app.api.schemas.contract import StateContract

    provider = provider_for("plan", Settings(llm_stages="plan:mock"))
    assert provider.name == "mock"
    fragment = json.loads(await provider.complete(system="s", user="u",
                                                  json_mode=True))
    assert fragment["dialogue_action"] == "ask_clarification"
    StateContract.model_validate(fragment)


class CountingProvider:
    """Test double that counts calls and can fail on demand."""

    name = "counting"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = 0

    async def complete(self, *, system, user, json_mode=False, max_tokens=512):
        self.calls += 1
        if self.fail:
            raise RuntimeError("backend down")
        return "ok"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_and_stops_calling_inner():
    clock = FakeClock()
    inner = CountingProvider(fail=True)
    breaker = BreakerProvider(inner, failure_threshold=3, cooldown_s=60.0,
                              clock=clock)
    assert breaker.name == "breaker(counting)"

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.complete(system="s", user="u")
    assert inner.calls == 3
    assert breaker.open is True

    with pytest.raises(LLMUnavailable, match="circuit open"):
        await breaker.complete(system="s", user="u")
    assert inner.calls == 3  # short-circuited, no network call


@pytest.mark.asyncio
async def test_breaker_closes_after_cooldown():
    clock = FakeClock()
    inner = CountingProvider(fail=True)
    breaker = BreakerProvider(inner, failure_threshold=2, cooldown_s=10.0,
                              clock=clock)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.complete(system="s", user="u")

    clock.now = 9.9
    with pytest.raises(LLMUnavailable):
        await breaker.complete(system="s", user="u")
    assert inner.calls == 2

    clock.now = 10.0
    inner.fail = False
    assert await breaker.complete(system="s", user="u") == "ok"
    assert inner.calls == 3
    assert breaker.open is False


@pytest.mark.asyncio
async def test_breaker_success_resets_failure_count():
    clock = FakeClock()
    inner = CountingProvider(fail=True)
    breaker = BreakerProvider(inner, failure_threshold=3, cooldown_s=60.0,
                              clock=clock)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.complete(system="s", user="u")
    inner.fail = False
    assert await breaker.complete(system="s", user="u") == "ok"

    inner.fail = True
    for _ in range(2):  # two fresh failures are below the threshold
        with pytest.raises(RuntimeError):
            await breaker.complete(system="s", user="u")
    assert breaker.open is False


def test_deps_wraps_only_structure_stage_in_breaker():
    settings = Settings(llm_stages="structure:mock,plan:mock")
    fast = deps._structure_provider(settings, thinking=False)
    assert isinstance(fast, BreakerProvider)
    assert isinstance(fast._inner, MockProvider)
    assert fast.name == "breaker(mock)"
    assert isinstance(deps._structure_provider(settings, thinking=True),
                      BreakerProvider)
    # The plan stage keeps its own retry/fallback chain, unwrapped.
    assert not isinstance(provider_for("plan", settings), BreakerProvider)
