"""LLM provider interface and shared HTTP plumbing."""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


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
        """Return raw model text. Raises on transport/API errors."""
        raise NotImplementedError


class ChatCompletionsProvider(LLMProvider):
    """Base for OpenAI-compatible /v1/chat/completions backends."""

    def __init__(self, base_url: str, model: str, timeout_s: float,
                 api_key: str = "",
                 transport: httpx.BaseTransport | None = None,
                 extra_body: dict | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._api_key = api_key
        self._transport = transport
        self._extra_body = extra_body or {}

    def payload(self, *, system: str, user: str,
                json_mode: bool, max_tokens: int) -> dict:
        body: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "stream": False,
            **self._extra_body,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout,
                                     transport=self._transport,
                                     headers=self.headers()) as client:
            response = await client.post(
                "/chat/completions",
                json=self.payload(system=system, user=user,
                                  json_mode=json_mode, max_tokens=max_tokens))
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
