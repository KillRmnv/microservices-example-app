import httpx
import pytest

from app.clients.llm import (
    FallbackProvider,
    LlamaCppProvider,
    MockProvider,
    OpenAICompatProvider,
    provider_for,
)
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
