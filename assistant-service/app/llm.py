"""LLM access behind one interface, backend chosen per pipeline stage.

Stages (see .env.example LLM_STAGES): structure / plan / telegram.
Backends: "ollama" (local) and "external" (any OpenAI-compatible API).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from .config import Settings


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 512,
    ) -> str:
        """Return the raw model text. Raises on transport/API errors."""
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._base = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout = settings.llm_timeout_s
        self._transport = transport

    def payload(self, *, system: str, user: str, max_tokens: int) -> dict:
        return {
            "model": self._model,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout,
                                     transport=self._transport) as client:
            response = await client.post("/api/generate",
                                         json=self.payload(system=system, user=user,
                                                            max_tokens=max_tokens))
            response.raise_for_status()
            return response.json().get("response", "")


class OpenAICompatProvider(LLMProvider):
    name = "external"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._base = settings.llm_external_base_url.rstrip("/")
        self._model = settings.llm_external_model
        self._api_key = settings.llm_external_api_key
        self._timeout = settings.llm_timeout_s
        self._transport = transport

    def payload(self, *, system: str, user: str,
                json_mode: bool, max_tokens: int) -> dict:
        body: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout,
                                     transport=self._transport,
                                     headers={"Authorization": f"Bearer {self._api_key}"}) as client:
            response = await client.post(
                "/chat/completions",
                json=self.payload(system=system, user=user,
                                  json_mode=json_mode, max_tokens=max_tokens))
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


def provider_for(stage: str, settings: Settings,
                 transport: httpx.BaseTransport | None = None) -> LLMProvider:
    backend = settings.backend_for(stage)
    if backend == "external":
        return OpenAICompatProvider(settings, transport=transport)
    if backend == "mock":
        return MockProvider(settings)
    return OllamaProvider(settings, transport=transport)


class MockProvider(LLMProvider):
    """Stand-in while Ling is not running: deterministic, no network.

    Returns a minimal ask_clarification contract fragment as JSON text.
    The caller (stage 3) validates it like any model output.
    """

    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        return ('{"dialogue_action": "ask_clarification", '
                '"needs_clarification": true, '
                '"clarification_prompt": "Мок провайдера: уточните дату и время"}')
