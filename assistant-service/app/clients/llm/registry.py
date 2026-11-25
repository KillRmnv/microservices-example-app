"""Provider registry + optional fallback chain.

``provider_for`` is a strategy registry, not a chain of ``if`` branches:
the backend name from settings selects a factory, and an unknown name fails
fast at startup instead of silently falling back to a default model.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import httpx

from ...core.config import Settings
from .base import LLMProvider, LLMUnavailable
from .llama_cpp import LlamaCppProvider
from .mock import MockProvider
from .openai_compat import OpenAICompatProvider
from .openrouter import OpenRouterProvider

log = logging.getLogger(__name__)


class UnknownBackend(ValueError):
    pass


def build_provider(backend: str, settings: Settings,
                   transport: httpx.BaseTransport | None = None,
                   thinking: bool | None = None) -> LLMProvider:
    """Build a provider, optionally forcing thinking on/off.

    ``thinking=None`` keeps the global ``llm_disable_thinking`` flag;
    ``thinking=False`` forces no-think mode (fast structure lane),
    ``thinking=True`` forces reasoning mode (plan stage).
    """
    if backend == "local":
        disable = (settings.llm_disable_thinking if thinking is None
                   else not thinking)
        return LlamaCppProvider(settings.llm_local_base_url,
                                settings.llm_local_model,
                                settings.llm_timeout_s, transport=transport,
                                disable_thinking=disable,
                                temperature=settings.llm_temperature,
                                top_p=settings.llm_top_p,
                                top_k=settings.llm_top_k)
    if backend == "external":
        return OpenAICompatProvider(settings.llm_external_base_url,
                                    settings.llm_external_model,
                                    settings.llm_external_api_key,
                                    settings.llm_timeout_s, transport=transport)
    if backend == "openrouter":
        if not settings.openrouter_key.strip() or not settings.openrouter_model.strip():
            raise UnknownBackend(
                "openrouter backend requires ASSISTANT_OPENROUTER_KEY and "
                "ASSISTANT_OPENROUTER_MODEL")
        return OpenRouterProvider(settings.openrouter_base_url,
                                  settings.openrouter_model,
                                  settings.openrouter_key,
                                  settings.llm_timeout_s,
                                  referer=settings.openrouter_referer,
                                  title=settings.openrouter_title,
                                  transport=transport)
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


class BreakerProvider(LLMProvider):
    """Stop calling a dead backend until the cooldown expires.

    A chat turn must fail fast when the model server is down: after
    ``failure_threshold`` consecutive errors the breaker opens and every call
    raises ``LLMUnavailable`` without touching the network until
    ``cooldown_s`` has elapsed. One successful call closes it again.
    """

    def __init__(self, inner: LLMProvider, *,
                 failure_threshold: int = 3,
                 cooldown_s: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._inner = inner
        self._threshold = max(1, failure_threshold)
        self._cooldown = max(0.0, cooldown_s)
        self._clock = clock
        self._failures = 0
        self._open_until: float | None = None
        self.name = f"breaker({inner.name})"

    @property
    def open(self) -> bool:
        return (self._open_until is not None
                and self._clock() < self._open_until)

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        if self.open:
            raise LLMUnavailable("circuit open")
        try:
            text = await self._inner.complete(
                system=system, user=user, json_mode=json_mode,
                max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001 — count any backend failure
            self._failures += 1
            if self._failures >= self._threshold:
                self._open_until = self._clock() + self._cooldown
                log.warning("LLM breaker opened for %s after %d failures: %s",
                            self._inner.name, self._failures, exc)
            raise
        self._failures = 0
        self._open_until = None
        return text


def _fallback_backend(primary: str, settings: Settings) -> str | None:
    if not settings.llm_fallback_enabled or primary == "mock":
        return None
    if primary == "local" and settings.llm_external_api_key:
        return "external"
    if primary == "external":
        return "local"
    return None


def provider_for(stage: str, settings: Settings,
                 transport: httpx.BaseTransport | None = None,
                 thinking: bool | None = None) -> LLMProvider:
    backend = settings.backend_for(stage)
    provider = build_provider(backend, settings, transport=transport,
                              thinking=thinking)
    secondary = _fallback_backend(backend, settings)
    if secondary is None:
        return provider
    return FallbackProvider([provider, build_provider(secondary, settings,
                                                      transport=transport)])
