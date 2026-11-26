"""External OpenAI-compatible backend ("external")."""
from __future__ import annotations

import httpx

from .base import ChatCompletionsProvider


class OpenAICompatProvider(ChatCompletionsProvider):
    name = "external"

    def __init__(self, base_url: str, model: str, api_key: str, timeout_s: float,
                 transport: httpx.BaseTransport | None = None) -> None:
        super().__init__(base_url, model, timeout_s, api_key=api_key,
                         transport=transport)
