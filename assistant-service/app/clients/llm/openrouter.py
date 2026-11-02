"""OpenRouter backend: one OpenAI-compatible API for chat stages.

OpenRouter serves many models behind /chat/completions, so the wire format is
shared with the OpenAI provider. The class only adds the attribution headers
OpenRouter recommends; the model and key come from configuration/secret env.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from .base import ChatCompletionsProvider

log = logging.getLogger(__name__)


class OpenRouterProvider(ChatCompletionsProvider):
    name = "openrouter"

    def __init__(self, base_url: str, model: str, api_key: str, timeout_s: float,
                 *, referer: str = "", title: str = "",
                 transport: httpx.BaseTransport | None = None) -> None:
        super().__init__(base_url, model, timeout_s, api_key=api_key,
                         transport=transport)
        self._referer = referer
        self._title = title

    def headers(self) -> dict:
        headers = super().headers()
        if self._referer:
            headers["HTTP-Referer"] = self._referer
        if self._title:
            headers["X-Title"] = self._title
        return headers

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                text = await super().complete(
                    system=system, user=user, json_mode=json_mode,
                    max_tokens=max_tokens)
                if text and text.strip():
                    return text
                # Some providers return 200 with empty content when the model
                # over-thinks. Retry once without forced JSON.
                text = await super().complete(
                    system=system, user=user, json_mode=False,
                    max_tokens=max_tokens)
                if text and text.strip():
                    return text
                raise RuntimeError("OpenRouter returned empty content")
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if 400 <= exc.response.status_code < 500 and json_mode:
                    # Model/router rejected response_format; prompt still
                    # asks for JSON, so retry without the forced format.
                    json_mode = False
                    continue
                if exc.response.status_code < 500 or attempt == 2:
                    raise
            except (httpx.RequestError, RuntimeError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
            await asyncio.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error
