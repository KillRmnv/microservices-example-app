"""Text embeddings (duplicate of collector's provider: separate deployable).

Backend is llama.cpp server mode (`llama server -m bge-m3-*.gguf --embedding`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
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
