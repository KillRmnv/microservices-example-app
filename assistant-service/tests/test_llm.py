import httpx
import pytest

from app.config import Settings
from app.llm import OllamaProvider, OpenAICompatProvider, provider_for


def make_settings(**overrides) -> Settings:
    base = {
        "ollama_base_url": "http://ollama:11434",
        "ollama_model": "qwen3:8b",
        "llm_external_base_url": "https://api.example.com/v1",
        "llm_external_api_key": "secret",
        "llm_external_model": "ext-model",
        "llm_stages": "structure:ollama,plan:external,telegram:external",
    }
    base.update(overrides)
    return Settings(**base)


def test_backend_for_stage_mapping():
    settings = make_settings()
    assert settings.backend_for("structure") == "ollama"
    assert settings.backend_for("plan") == "external"
    assert settings.backend_for("unknown-stage") == "ollama"


def test_provider_for_selects_backend():
    settings = make_settings()
    assert isinstance(provider_for("structure", settings), OllamaProvider)
    assert isinstance(provider_for("plan", settings), OpenAICompatProvider)


def test_ollama_payload_shape():
    provider = OllamaProvider(make_settings())
    payload = provider.payload(system="sys", user="hi", max_tokens=64)
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False
    assert payload["options"]["num_predict"] == 64


def test_openai_payload_json_mode():
    provider = OpenAICompatProvider(make_settings())
    payload = provider.payload(system="sys", user="hi", json_mode=True, max_tokens=64)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0] == {"role": "system", "content": "sys"}


@pytest.mark.asyncio
async def test_ollama_complete_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": "{\"a\": 1}"})

    provider = OllamaProvider(make_settings(), transport=httpx.MockTransport(handler))
    text = await provider.complete(system="sys", user="hi", json_mode=True)
    assert text == "{\"a\": 1}"


@pytest.mark.asyncio
async def test_openai_complete_uses_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": "done"}}]})

    provider = OpenAICompatProvider(make_settings(), transport=httpx.MockTransport(handler))
    text = await provider.complete(system="sys", user="hi")
    assert text == "done"
