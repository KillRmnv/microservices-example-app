"""Local llama.cpp server backend ("local").

llama.cpp exposes an OpenAI-compatible ``/v1/chat/completions`` endpoint, so
the wire format is shared with the external provider. The class stays
separate because the base URL/model defaults and semantics differ.
"""
from __future__ import annotations

import httpx

from .base import ChatCompletionsProvider


class LlamaCppProvider(ChatCompletionsProvider):
    name = "local"

    def __init__(self, base_url: str, model: str, timeout_s: float,
                 transport: httpx.BaseTransport | None = None) -> None:
        super().__init__(base_url, model, timeout_s, transport=transport)


# Backward-compatible alias for callers that still import the old name.
LlamaServerChatProvider = LlamaCppProvider
