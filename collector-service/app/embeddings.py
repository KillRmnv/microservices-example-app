"""Text embeddings behind one interface.

Production backend is llama.cpp server mode (`llama server -m bge-m3-*.gguf
--embedding`), OpenAI-compatible /v1/embeddings. No torch in our images.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per input text, in order. Raises on errors."""
        raise NotImplementedError


class LlamaServerEmbedding(EmbeddingProvider):
    def __init__(self, base_url: str, dim: int = 1024,
                 timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._base = base_url.rstrip("/")
        self.dim = dim
        self._timeout = timeout_s
        self._transport = transport

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout,
                                     transport=self._transport) as client:
            response = await client.post("/v1/embeddings", json={"input": texts})
            response.raise_for_status()
            items = sorted(response.json()["data"], key=lambda row: row["index"])
            vectors = [row["embedding"] for row in items]
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"embedding count mismatch: {len(vectors)} != {len(texts)}")
        return vectors


def embeddable_text(title: str, venue: str | None, description: str | None) -> str:
    """What goes into the vector: atmosphere-relevant text, not filters."""
    parts = [title]
    if venue:
        parts.append(venue)
    if description:
        parts.append(description[:1000])
    return "\n".join(parts)
