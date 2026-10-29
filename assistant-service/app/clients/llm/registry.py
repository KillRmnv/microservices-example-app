"""Provider registry + optional fallback chain.

``provider_for`` is a strategy registry, not a chain of ``if`` branches:
the backend name from settings selects a factory, and an unknown name fails
fast at startup instead of silently falling back to a default model.
"""
from __future__ import annotations

import logging

import httpx

from ...core.config import Settings
from .base import LLMProvider
from .llama_cpp import LlamaCppProvider
from .mock import MockProvider
from .openai_compat import OpenAICompatProvider

log = logging.getLogger(__name__)


class UnknownBackend(ValueError):
    pass


def build_provider(backend: str, settings: Settings,
                   transport: httpx.BaseTransport | None = None) -> LLMProvider:
    if backend == "local":
        return LlamaCppProvider(settings.llm_local_base_url,
                                settings.llm_local_model,
                                settings.llm_timeout_s, transport=transport,
                                disable_thinking=settings.llm_disable_thinking)
    if backend == "external":
        return OpenAICompatProvider(settings.llm_external_base_url,
                                    settings.llm_external_model,
                                    settings.llm_external_api_key,
                                    settings.llm_timeout_s, transport=transport)
    if backend == "mock":
        return MockProvider()
    raise UnknownBackend(f"unknown LLM backend: {backend!r}")


class FallbackProvider(LLMProvider):
    """Try providers in order; only transport/API errors move to the next."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("fallback chain needs at least one provider")
        self._providers = providers
        self.name = "fallback(" + "->".join(provider.name for provider in providers) + ")"

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.complete(
                    system=system, user=user,
                    json_mode=json_mode, max_tokens=max_tokens)
            except Exception as exc:  # noqa: BLE001 — fallback by design
                last_error = exc
                log.warning("LLM backend %s failed: %s", provider.name, exc)
        assert last_error is not None
        raise last_error


def _fallback_backend(primary: str, settings: Settings) -> str | None:
    if not settings.llm_fallback_enabled or primary == "mock":
        return None
    if primary == "local" and settings.llm_external_api_key:
        return "external"
    if primary == "external":
        return "local"
    return None


def provider_for(stage: str, settings: Settings,
                 transport: httpx.BaseTransport | None = None) -> LLMProvider:
    backend = settings.backend_for(stage)
    provider = build_provider(backend, settings, transport=transport)
    secondary = _fallback_backend(backend, settings)
    if secondary is None:
        return provider
    return FallbackProvider([provider, build_provider(secondary, settings,
                                                      transport=transport)])
